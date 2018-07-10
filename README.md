
## Introduction

C/C++ code completion plugin for [ncm2](https://github.com/ncm2/ncm2)

This plugin is based on [libclang python
binding](https://github.com/llvm-mirror/clang). Inspired by
[clang_complete](https://github.com/Rip-Rip/clang_complete).

## Config

### loading `libclang.so`

```vim
" path to directory where libclang.so can be found
let g:ncm2_pyclang#library_path = '/usr/lib/llvm-5.0/lib'

" or path to the libclang.so file
let g:ncm2_pyclang#library_path = '/usr/lib64/libclang.so.5.0'

```

### loading `compile_commands.json`

```
" a list of relative paths for compile_commands.json
let g:ncm2_pyclang#database_path = [
            \ 'compile_commands.json',
            \ 'build/compile_commands.json'
            \ ]
```

### loading `.clang_complete`

If your build system doesn't generate `compile_commands.json`, you could put a
`.clang_complete` file into your project directory, which sould contain
something like:

```
-DDEBUG
-include ../config.h
-I../common
```

```vim
" a list of relative paths looking for .clang_complete
let g:ncm2_pyclang#args_file_path = ['.clang_complete']
```

### Goto Declaration

```vim
    autocmd FileType c,cpp nnoremap <buffer> gd :<c-u>call ncm2_pyclang#goto_declaration()<cr>
```
