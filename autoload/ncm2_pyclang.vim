if get(s:, 'loaded', 0)
    finish
endif
let s:loaded = 1

let g:ncm2_pyclang#library_path = get(g:,
            \ 'ncm2_pyclang#library_path',
            \ '')

let g:ncm2_pyclang#database_path = get(g:,
            \ 'ncm2_pyclang#database_path',
            \ [
            \   'compile_commands.json',
            \   'build/compile_commands.json'
            \   ])

let g:ncm2_pyclang#proc = yarp#py3('ncm2_pyclang_proc')

let g:ncm2_pyclang#bin = get(g:, 'ncm2_pyclang#bin', "bin/ncm2_pyclang")

let g:ncm2_pyclang#source = get(g:, 'ncm2_pyclang#source', {
            \ 'name': 'pyclang',
            \ 'scope': ['cpp', 'c'],
            \ 'priority': 9,
            \ 'mark': 'cxx',
            \ 'on_complete': 'ncm2_pyclang#on_complete',
            \ 'on_warmup': 'ncm2_pyclang#on_warmup',
            \ 'complete_pattern': ['-\>', '::', '\.']
            \ })

let g:ncm2_pyclang#source = extend(g:ncm2_pyclang#source,
            \ get(g:, 'ncm2_pyclang#source_override', {}),
            \ 'force')

func! ncm2_pyclang#init()
    call ncm2#register_source(g:ncm2_pyclang#source)
endfunc

func! ncm2_pyclang#_proc_started()
    call ncm2_pyclang#on_warmup(ncm2#context())
endfunc

func! ncm2_pyclang#on_warmup(ctx)
    if &filetype != 'cpp' && filetype != 'c'
        call g:ncm2_pyclang#proc.jobstart()
        return
    endif
    if a:ctx['filepath'] == ""
        call g:ncm2_pyclang#proc.jobstart()
        return
    endif

    call g:ncm2_pyclang#proc.try_notify('cache_add',
                \ a:ctx,
                \ ncm2_pyclang#_data(),
                \ getline(1, '$'))

    if get(b:, 'b:ncm2_pyclang_cache') == 0
        au BufDelete <buffer> call 
                    \ g:ncm2_pyclang#proc.try_notify(
                    \   'cache_del',
                    \   expand('%:p'))
    endif

    let b:ncm2_pyclang_cache = 1
endfunc

func! ncm2_pyclang#on_complete(ctx)
    call g:ncm2_pyclang#proc.try_notify('on_complete',
                \ a:ctx,
                \ ncm2_pyclang#_data(),
                \ getline(1, '$'))
endfunc

func! ncm2_pyclang#_data()
    return  {'cwd': getcwd(),
                \ 'database_path': g:ncm2_pyclang#database_path,
                \ }
endfunc

