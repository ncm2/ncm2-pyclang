#include "clang-c/Index.h"

#include <string>
#include <vector>
#include <memory>
#include <map>
#include <tuple>
#include <iostream>

#include "json.hpp"

using namespace std;
using nlohmann::json;

typedef shared_ptr<CXTranslationUnitImpl> TranslationUnitSP;
typedef shared_ptr<CXCodeCompleteResults> CodeCompleteResultsSP;

class LibClang
{
public:
    LibClang() { idx_ = clang_createIndex(1, 1); }

    LibClang(const LibClang &&) = delete;
    LibClang &operator=(const LibClang &&) = delete;

    ~LibClang() { clang_disposeIndex(idx_); }

    void add_tu_cache(const string &lang,
                      const string &fpath,
                      const string &src,
                      const vector<string> &args)
    {
        auto iter = cache_.find(fpath);
        if (iter != cache_.end()) {
            auto &c = iter->second;
            if (get<0>(c) == args) {
                auto tu = get<1>(c);
                update_tu(tu, lang, fpath, src);
                return;
            }
        }

        auto tu = create_tu(lang, fpath, src, args);

        if (!tu)
            return;

        cache_[fpath] = make_tuple(args, tu);
        return;
    }

    void remove_tu_cache(const string &fpath) { cache_.erase(fpath); }

    // get tu from cache, or create a new tu
    TranslationUnitSP get_tu(const string &lang,
                             const string &fpath,
                             const string &src,
                             const vector<string> &args,
                             bool *cache_hit = nullptr)
    {
        auto iter = cache_.find(fpath);
        if (iter == cache_.end()) {
            if (cache_hit)
                *cache_hit = false;
            return create_tu(lang, fpath, src, args);
        }

        // check args
        auto &c = iter->second;
        if (get<0>(c) != args) {
            if (cache_hit)
                *cache_hit = false;
            return create_tu(lang, fpath, src, args);
        }

        if (cache_hit)
            *cache_hit = true;
        return get<1>(c);
    }

    CodeCompleteResultsSP complete_at(string lang,
                                      const string &fpath,
                                      const string &src,
                                      const vector<string> &args,
                                      int64_t lnum,
                                      int64_t bcol,
                                      bool* cache_hit = nullptr)
    {
        vector<const char *> vc_args;
        for (auto const &arg : args) {
            vc_args.push_back(arg.c_str());
        }

        vector<struct CXUnsavedFile> vc_unsavedf(1);
        auto &f = vc_unsavedf[0];
        f.Contents = src.c_str();
        f.Length = src.length();
        f.Filename = fpath.c_str();

        auto tu = get_tu(lang, fpath, src, args, cache_hit);

        unsigned flags = clang_defaultCodeCompleteOptions();
        auto results = clang_codeCompleteAt(tu.get(),
                                            fpath.c_str(),
                                            lnum,
                                            bcol,
                                            vc_unsavedf.data(),
                                            vc_unsavedf.size(),
                                            flags);
        CodeCompleteResultsSP completions(results,
                                          clang_disposeCodeCompleteResults);
        return completions;
    }

private:
    TranslationUnitSP create_tu(const string &lang,
                                const string &fpath,
                                const string &src,
                                const vector<string> &args)
    {
        vector<const char *> vc_args;
        for (auto const &arg : args) {
            vc_args.push_back(arg.c_str());
        }

        vector<struct CXUnsavedFile> vc_unsavedf(1);
        auto &f = vc_unsavedf[0];
        f.Contents = src.c_str();
        f.Length = src.length();
        f.Filename = fpath.c_str();

        // TODO compare with the clang_createTranslationUnitFromSourceFile
        // clang_createTranslationUnitFromSourceFile seems to be an old API
        // http://clang-developers.42468.n3.nabble.com/Diff-between-createTranslationUnit-and-parseTranslationUnit-td3581094.html
        unsigned tu_flags = clang_defaultEditingTranslationUnitOptions();
        // auto tu = clang_createTranslationUnitFromSourceFile(idx_,
        //                                                     fpath.c_str(),
        //                                                     vc_args.size(),
        //                                                     vc_args.data(),
        //                                                     vc_unsavedf.size(),
        //                                                     vc_unsavedf.data());

        tu_flags |= CXTranslationUnit_CacheCompletionResults;

        auto tu = clang_parseTranslationUnit(idx_,
                                             fpath.c_str(),
                                             vc_args.data(),
                                             vc_args.size(),
                                             vc_unsavedf.data(),
                                             vc_unsavedf.size(),
                                             tu_flags);
        return TranslationUnitSP(tu, clang_disposeTranslationUnit);
    }

    void update_tu(TranslationUnitSP tu, string lang, string fpath, string src)
    {
        auto opts = clang_defaultReparseOptions(tu.get());

        vector<struct CXUnsavedFile> vc_unsavedf(1);
        auto &f = vc_unsavedf[0];
        f.Contents = src.c_str();
        f.Length = src.length();
        f.Filename = fpath.c_str();

        clang_reparseTranslationUnit(
            tu.get(), vc_unsavedf.size(), vc_unsavedf.data(), opts);
    }

    map<string, tuple<vector<string>, TranslationUnitSP>> cache_;
    CXIndex idx_;
};

struct CmdHandler
{
    shared_ptr<LibClang> libclang_ = make_shared<LibClang>();

    void run()
    {
        while (true) {
            string line;
            getline(cin, line);
            json req = json::parse(line);
            string cmd = req["command"];
            json rsp;
            if (cmd == "cache_file") {
                rsp = cmd_cache_file(req);
            } else if (cmd == "code_completion") {
                rsp = cmd_code_completion(req);
            } else {
                rsp = json::object();
                rsp["result"] = 0;
                rsp["message"] = "unsupported command";
            }
            cout << rsp.dump() << std::endl;
        }
    }

    json cmd_cache_file(json req)
    {
        json ctx = req["context"];
        string fpath = ctx["filepath"];

        const string &src = req["src"];
        vector<string> args;
        if (req["args"].is_array()) {
            vector<string> tmp = req["args"];
            args = tmp;
        }

        string scope = ctx["scope"];
        string lang;
        if (scope == "cpp") {
            lang = "c++";
        } else {
            lang = "c";
        }

        libclang_->add_tu_cache(lang, fpath, src, args);

        return {};
    }

    json cmd_code_completion(json req)
    {
        json ctx = req["context"];
        int64_t lnum = ctx["lnum"];
        int64_t bcol = ctx["bcol"];
        string fpath = ctx["filepath"];

        const string &src = req["src"];
        vector<string> args;
        if (req["args"].is_array()) {
            vector<string> tmp = req["args"];
            args = tmp;
        }

        string scope = ctx["scope"];
        string lang;
        if (scope == "cpp") {
            lang = "c++";
        } else {
            lang = "c";
        }

        bool cache_hit = false;
        auto res = libclang_->complete_at(lang, fpath, src, args, lnum, bcol, &cache_hit);

        json matches = json::array();
        for (size_t i = 0; i < res->NumResults; ++i) {
            json item = parse_completion_result(res->Results[i]);
            matches.push_back(item);
        }
        auto rsp = json::object();
        rsp["matches"] = matches;
        rsp["cache_hit"] = cache_hit;
        return rsp;
    }

    json parse_completion_result(CXCompletionResult &completion)
    {
        json item;
        CXCursorKind cursor_kind = completion.CursorKind;
        CXCompletionString cmpl_string = completion.CompletionString;
        size_t chunks = clang_getNumCompletionChunks(cmpl_string);
        for (size_t i = 0; i < chunks; ++i) {
            CXCompletionChunkKind chunk_kind =
                clang_getCompletionChunkKind(cmpl_string, i);
            CXString chunk_text = clang_getCompletionChunkText(cmpl_string, i);
            string text = clang_getCString(chunk_text);
            if (chunk_kind == CXCompletionChunk_TypedText) {
                item["word"] = text;
                continue;
            }
        }
        return item;
    }
};

int main(void)
{
    CmdHandler handler;
    handler.run();
    return 0;
}
