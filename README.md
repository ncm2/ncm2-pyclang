
## Install

Here's the command for install requirements on Debian:

```bash
sudo apt install g++ nlohmann-json-dev libclang-5.0-dev
```

Then `cd` to the the plugin directory and compile the binary.

```bash
cd ncm2-libclang
g++ src/ncm2_libclang.cpp -std=c++11 -I /usr/lib/llvm-5.0/include/ /usr/lib/llvm-5.0/lib/libclang.so -o bin/ncm2_libclang
```

Here's the installation vimrc for
[vim-plug](https://github.com/junegunn/vim-plug).

```vim
Plug "ncm2/ncm2-libclang", {"do": "g++ src/ncm2_libclang.cpp -std=c++11 -I /usr/lib/llvm-5.0/include/ /usr/lib/llvm-5.0/lib/libclang.so -o bin/ncm2_libclang"}
```

