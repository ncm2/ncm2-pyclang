
LIBCLANG_PREFIX?=/usr/lib/llvm-5.0

bin/ncm2_libclang: src/ncm2_libclang.cpp
	g++ -std=c++11 -I $(LIBCLANG_PREFIX)/include/ $(LIBCLANG_PREFIX)/lib/libclang.so $^ -o $@

