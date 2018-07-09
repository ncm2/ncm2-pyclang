
## Introduction

C/C++ completion based on [libclang python
binding](https://github.com/llvm-mirror/clang). Inspired by
[clang_complete](https://github.com/Rip-Rip/clang_complete)

## Config

```vim
" path to directory where libclang.so can be found
let g:ncm2_pyclang#library_path = '/usr/lib/llvm-5.0/lib'

" or path to the libclang.so file
let g:ncm2_pyclang#library_path = '/usr/lib64/libclang.so.5.0'

" a list of relative paths for compile_commands.json
let g:ncm2_pyclang#database_path = [
            \ 'compile_commands.json',
            \ 'build/compile_commands.json'
            \ ]
```

If your build system doesn't generate `compile_commands.json`, you could put a
`.clang_complete` file into your project directory, which sould contain
something like:

```
-DDEBUG
-include ../config.h
-I../common
```

### Goto Declaration

```vim
    autocmd FileType c,cpp nnoremap <buffer> gd :<c-u>call ncm2_pyclang#goto_declaration()<cr>
```
