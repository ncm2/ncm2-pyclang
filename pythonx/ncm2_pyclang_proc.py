# -*- coding: utf-8 -*-

from ncm2 import Ncm2Source, getLogger, Popen
import subprocess
import re
from os.path import dirname
from os import path
import vim
import json
import time

import sys
sys.path.insert(0, path.join(dirname(__file__), '3rd'))

from ncm2_pyclang import args_from_cmake, args_from_clang_complete
from clang import cindex
from clang.cindex import CodeCompletionResult, CompletionString, SourceLocation, Cursor, File

logger = getLogger(__name__)


class Source(Ncm2Source):

    def __init__(self, nvim):
        Ncm2Source.__init__(self, nvim)

        library_path = nvim.vars['ncm2_pyclang#library_path']
        if path.isdir(library_path):
            cindex.Config.set_library_path(library_path)
        elif path.isfile(library_path):
            cindex.Config.set_library_file(library_path)

        cindex.Config.set_compatibility_check(False)

        self.index = cindex.Index.create(excludeDecls=False)
        self.tu_cache = {}
        self.notify("ncm2_pyclang#_proc_started")

    def notify(self, method: str, *args):
        self.nvim.call(method, *args, async_=True)

    def get_args_dir(self, ncm2_ctx, data):
        cwd = data['cwd']
        database_path = data['database_path']
        filepath = ncm2_ctx['filepath']
        args_file_path = data['args_file_path']

        args = []

        if 'scope' in ncm2_ctx and ncm2_ctx['scope'] == 'cpp':
            args.append('-xc++')
        elif ncm2_ctx['filetype'] == 'cpp':
            args.append('-xc++')
        else:
            args.append('-xc')

        run_dir = cwd
        cmake_args, directory = args_from_cmake(filepath, cwd, database_path)
        if cmake_args is not None:
            args = cmake_args
            run_dir = directory
        else:
            clang_complete_args, directory = args_from_clang_complete(
                filepath, cwd, args_file_path)
            if clang_complete_args:
                args = clang_complete_args
                run_dir = directory

        args.insert(0, '-working-directory=' + run_dir)

        return [args, run_dir]

    def cache_add(self, ncm2_ctx, data, lines):
        src = self.get_src("\n".join(lines), ncm2_ctx)
        filepath = ncm2_ctx['filepath']
        changedtick = ncm2_ctx['changedtick']
        args, directory = self.get_args_dir(ncm2_ctx, data)
        start = time.time()

        check = dict(args=args, directory=directory)
        if filepath in self.tu_cache:
            cache = self.tu_cache[filepath]
            if check == cache['check']:
                tu = cache['tu']
                if changedtick == cache['changedtick']:
                    logger.info("changedtick is the same, skip reparse")
                    return
                self.reparse_tu(tu, filepath, src)
                logger.debug("cache_add reparse existing done")
                return
            del self.tu_cache[filepath]

        cache = {}
        cache['check'] = check
        cache['changedtick'] = changedtick

        tu = self.create_tu(filepath, args, directory, src)
        cache['tu'] = tu

        self.tu_cache[filepath] = cache

        # An explicit reparse speeds up the completion significantly. I
        # don't know why
        self.reparse_tu(tu, filepath, src)

        end = time.time()
        logger.debug("cache_add done. time: %s", end - start)

    def cache_del(self, filepath):
        if filepath in self.tu_cache:
            del self.tu_cache[filepath]

    def get_tu(self, filepath, args, directory, src):
        check = dict(args=args, directory=directory)
        if filepath in self.tu_cache:
            cache = self.tu_cache[filepath]
            tu = cache['tu']
            if check == cache['check']:
                logger.info("%s tu is cached", filepath)
                self.reparse_tu(tu, filepath, src)
                return cache['tu']
            logger.info("%s tu invalidated by check %s -> %s",
                        check, cache['check'])
            self.cache_del(filepath)
        logger.info("cache miss")
        return self.create_tu(filepath, args, directory, src)

    def create_tu(self, filepath, args, directory, src):
        CXTranslationUnit_KeepGoing = 0x200

        flags = cindex.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE | \
            cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD | \
            cindex.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS | \
            cindex.TranslationUnit.PARSE_INCOMPLETE | \
            CXTranslationUnit_KeepGoing

        logger.info("flags %s", flags)

        unsaved = (filepath, src)
        return self.index.parse(filepath, args, [unsaved], flags)

    def reparse_tu(self, tu, filepath, src):
        unsaved = (filepath, src)
        tu.reparse([unsaved])

    def on_complete(self, ncm2_ctx, data, lines):
        src = self.get_src("\n".join(lines), ncm2_ctx)
        filepath = ncm2_ctx['filepath']
        startccol = ncm2_ctx['startccol']
        bcol = ncm2_ctx['bcol']
        lnum = ncm2_ctx['lnum']
        base = ncm2_ctx['base']

        args, directory = self.get_args_dir(ncm2_ctx, data)

        start = time.time()

        if ncm2_ctx['scope'] != ncm2_ctx['filetype']:
            if ncm2_ctx['scope'] == 'cpp':
                filepath += '.cpp'
            else:
                filepath += '.c'

        tu = self.get_tu(filepath, args, directory, src)

        CXCodeComplete_IncludeMacros = 0x01
        CXCodeComplete_IncludeCodePatterns = 0x02

        cmpl_flags = CXCodeComplete_IncludeMacros | \
            CXCodeComplete_IncludeCodePatterns

        unsaved = [filepath, src]
        cr = tu.codeComplete(filepath, lnum, bcol, [unsaved], cmpl_flags)
        results = cr.results

        cr_end = time.time()

        matcher = self.matcher_get(ncm2_ctx['matcher'])

        matches = []
        for res in results:
            item = self.format_complete_item(res)
            # filter it's kind of useless for completion
            if item['word'].startswith('operator '):
                continue
            item = self.match_formalize(ncm2_ctx, item)
            if not matcher(base, item):
                continue
            matches.append(item)

        end = time.time()
        logger.debug("total time: %s, codeComplete time: %s, matches %s -> %s",
                     end - start, cr_end - start, len(results), len(matches))

        self.complete(ncm2_ctx, startccol, matches)

    def format_complete_item(self, result: CodeCompletionResult):
        result_type = None
        word = ""
        snippet = ""
        info = ""

        def roll_out_optional(chunks: CompletionString):
            result = []
            word = ""
            for chunk in chunks:
                if chunk.isKindInformative():
                    continue
                if chunk.isKindResultType():
                    continue
                if chunk.isKindTypedText():
                    continue
                word += chunk.spelling
                if chunk.isKindOptional():
                    result += roll_out_optional(chunk.string)
            return [word] + result

        placeholder_num = 1

        for chunk in result.string:

            if chunk.isKindInformative():
                continue

            if chunk.isKindResultType():
                result_type = chunk
                continue

            chunk_text = chunk.spelling
            if chunk.isKindTypedText():
                word = chunk_text

            if chunk.isKindOptional():
                for arg in roll_out_optional(chunk.string):
                    snippet += self.lsp_snippet_placeholder(
                        placeholder_num, arg)
                    placeholder_num += 1
                    info += "[" + arg + "]"
            elif chunk.isKindPlaceHolder():
                snippet += self.lsp_snippet_placeholder(
                    placeholder_num, chunk_text)
                placeholder_num += 1
                info += chunk_text
            else:
                snippet += chunk_text
                info += chunk_text

        menu = info

        if result_type:
            result_text = result_type.spelling
            menu = result_text + " " + menu

        completion = dict()
        completion['word'] = word
        ud = {}
        if snippet != word:
            ud['is_snippet'] = 1
            ud['snippet'] = snippet
        completion['user_data'] = ud
        completion['menu'] = menu
        completion['info'] = info
        completion['dup'] = 1
        return completion

    def lsp_snippet_placeholder(self, num, txt=''):
        txt = txt.replace('\\', '\\\\')
        txt = txt.replace('$', r'\$')
        txt = txt.replace('}', r'\}')
        if txt == '':
            return '${%s}' % num
        return '${%s:%s}' % (num, txt)

    def find_declaration(self, ncm2_ctx, data, lines):
        src = self.get_src("\n".join(lines), ncm2_ctx)
        filepath = ncm2_ctx['filepath']
        bcol = ncm2_ctx['bcol']
        lnum = ncm2_ctx['lnum']

        args, directory = self.get_args_dir(ncm2_ctx, data)

        tu = self.get_tu(filepath, args, directory, src)

        f = File.from_name(tu, filepath)
        location = SourceLocation.from_position(tu, f, lnum, bcol)
        cursor = Cursor.from_location(tu, location)

        defs = [cursor.get_definition(), cursor.referenced]
        for d in defs:
            if d is None:
                logger.info("d None")
                continue

            d_loc = d.location
            if d_loc.file is None:
                logger.info("location.file None")
                continue

            ret = {}
            ret['file'] = d_loc.file.name
            ret['lnum'] = d_loc.line
            ret['bcol'] = d_loc.column
            return ret
        return {}


source = Source(vim)

on_complete = source.on_complete
cache_add = source.cache_add
find_declaration = source.find_declaration
cache_del = source.cache_del
get_args_dir = source.get_args_dir
