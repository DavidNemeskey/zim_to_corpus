# Compiles zim_to_dir. Note that you need a g++ version that _properly_
# supports c++17; that is, version 8 or above.
CXX_VER := $(shell $(CXX) --version | head -1 | sed -e "s/.* //" -e "s/\..*//")
ifeq ($(shell expr $(CXX_VER) \>= 8), 0)
$(error $(CXX) should at least be of version 8 for proper support of c++17)
endif

CPPFLAGS=-g -O3 -I cxxopts/include/ -I zstr/src/ -I spdlog/include -std=c++17
# Static libstdc++ can be removed if the target machine has the same or
# newer GLIBCXX version
LDFLAGS=-g -static-libstdc++
LDLIBS=$(if $(findstring 8,$(CXX_VER)), -lstdc++fs) -l:libzim.a -l:liblzma.a -l:libzstd.a -lz -pthread

SRCS=zim_to_dir.cpp
OBJS=$(subst .cpp,.o,$(SRCS))

all: zim_to_dir clean

zim_to_dir: $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LDLIBS)

%.o: %.cpp
	$(CXX) $(CPPFLAGS) -c $<

clean:
	rm -f $(OBJS)

distclean: clean
	rm -f zim_to_dir
