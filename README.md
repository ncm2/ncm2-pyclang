
## Introduction

C/C++ code completion plugin for [ncm2](https://github.com/ncm2/ncm2)

This plugin is based on [libclang python
binding](https://github.com/llvm-mirror/clang). Inspired by
[clang_complete](https://github.com/Rip-Rip/clang_complete).

Features:

- Support CMake or similar build systems that generate `compile_commands.json`
- Support `.clang_complete` like [clang-complete](https://github.com/Rip-Rip/clang_complete)
- Support Kbuild for linux kernel and u-boot, it generates something like
  `init/.main.o.cmd`
- Support goto declaration. (not goto definition)
- Support #include completion.

## Config

### `g:ncm2_pyclang#library_path`

Use `g:ncm2_pyclang#library_path` to specify the directory of libclang library
or the file itself, e.g., for Linux:

```vim
" path to directory where libclang.so can be found
let g:ncm2_pyclang#library_path = '/usr/lib/llvm-5.0/lib'

" or path to the libclang.so file
let g:ncm2_pyclang#library_path = '/usr/lib64/libclang.so.5.0'
```

Notes:

- Different operating systems normally have their own extensions for the
  libclang file.

    - Linux: libclang.so
    - macOS: libclang.dylib
    - Windows: libclang.dll

- Sometimes ncm2-pyclang still works even you don't set
  `g:ncm2_pyclang#library_path`, that's because another libclang is found,
  which is probably the system libclang. The system libclang is often a bit
  old and is not guranteed to always be found, so I highly recommend set
  `g:ncm_clang#library_path` explicitly.

### `g:ncm2_pyclang#database_path`

Usually, invoking cmake with option
[-DCMAKE_EXPORT_COMPILE_COMMANDS=ON](https://cmake.org/cmake/help/v3.5/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html)
generates the compilation database `compile_commands.json`.

The config `g:ncm2_pyclang#database_path` tells this plugin where to look for
compilation database.

```vim
" a list of relative paths for compile_commands.json
let g:ncm2_pyclang#database_path = [
            \ 'compile_commands.json',
            \ 'build/compile_commands.json'
            \ ]
```

### `g:ncm2_pyclang#args_file_path`

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

### `g:ncm2_pyclang#gcc_path`

This option defaults to `gcc`. For some reason (I don't know), clang does not
handle c++ builtin headers. This plugin uses `gcc -xc++ -E -Wp,-v -` to get a
list of system header path.

If `gcc` is not available on your system, this plugin fallbacks to options
definged in `g:ncm2_pyclang#sys_inc_args_fallback`.

You can open a C/C++ file, then execute `:echo ncm2_pyclang#get_args_dir()` to
print the compiler arguments picked and passed to libclang.

### Goto Declaration

```vim
    autocmd FileType c,cpp nnoremap <buffer> gd :<c-u>call ncm2_pyclang#goto_declaration()<cr>
```

