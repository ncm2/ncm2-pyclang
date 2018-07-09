if get(s:, 'loaded', 0)
    finish
endif
let s:loaded = 1

let g:ncm2_libclang#database_path = get(g:,
            \ 'ncm2_libclang#database_path',
            \ [
            \   'compile_commands.json',
            \   'build/compile_commands.json'
            \   ])

let g:ncm2_libclang#proc = yarp#py3('ncm2_libclang_proc')

let g:ncm2_libclang#bin = get(g:, 'ncm2_libclang#bin', "bin/ncm2_libclang")

let g:ncm2_libclang#source = get(g:, 'ncm2_libclang#source', {
            \ 'name': 'clang',
            \ 'scope': ['cpp', 'c'],
            \ 'priority': 9,
            \ 'mark': 'cxx',
            \ 'on_complete': 'ncm2_libclang#on_complete',
            \ 'on_warmup': 'ncm2_libclang#on_warmup',
            \ 'complete_pattern': ['-\>', '::', '\.']
            \ })

let g:ncm2_libclang#source = extend(g:ncm2_libclang#source,
            \ get(g:, 'ncm2_libclang#source_override', {}),
            \ 'force')

func! ncm2_libclang#init()
    call ncm2#register_source(g:ncm2_libclang#source)
endfunc

func! ncm2_libclang#on_warmup(ctx)
    if &filetype != 'cpp' && filetype != 'c'
        call g:ncm2_libclang#proc.jobstart()
        return
    endif
    if a:ctx['filepath'] == ""
        call g:ncm2_libclang#proc.jobstart()
        return
    endif

    call g:ncm2_libclang#proc.try_notify('cache_file',
                \ a:ctx,
                \ getline(1, '$'),
                \ ncm2_libclang#_ctx())
endfunc

func! ncm2_libclang#on_complete(ctx)
    call g:ncm2_libclang#proc.try_notify('on_complete',
                \ a:ctx,
                \ getline(1, '$'),
                \ ncm2_libclang#_ctx())
endfunc

func! ncm2_libclang#msg(msg)
    echom 'ncm2_libclang: ' . a:msg
endfunc

fun! ncm2_libclang#compilation_info()
    py3 << EOF
import vim
import ncm2_libclang
from os import path
filepath = vim.eval("expand('%:p')")
filedir = path.dirname(filepath)
ctx = vim.eval("ncm2_libclang#_ctx()")
cwd = ctx['cwd']
database_path = ctx['database_path']
args, directory = ncm2_libclang.args_from_cmake(filepath, cwd, database_path)
if not args:
    args, directory = ncm2_libclang.args_from_clang_complete(filepath, cwd)
ret = dict(args=args or [], directory=directory or cwd)
ret['args'] = ['-I' + filedir] + ret['args']
EOF
    return py3eval('ret')
endf

func! ncm2_libclang#_ctx()
    return  {'cwd': getcwd(),
                \ 'database_path': g:ncm2_libclang#database_path,
                \ }
endfunc

