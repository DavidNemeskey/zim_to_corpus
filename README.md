# zim_to_corpus

Scripts to extract the text from (mostly) Wikipedia pages from .zim archives.

## `zim_to_dir`

`zim_to_dir` is a C++ program that reads a Wikipedia .zim file and extracts
all valid articles in it to files in a(n existing or newly created) directory.
For now, it only works for Wikipedia dumps downloaded from the
[Kiwix archives](https://wiki.kiwix.org/wiki/Content_in_all_languages).

An article is deemed valid if it is

- in the article namespace (`A`)
- not marked as deleted
- not a redirect
- not a disambiguation page

### Suppored languages

As of now, only English and Hungarian dumps are supported. However, "support"
for other languages can be added easily by modifying a very obvious line in
`zim_to_dir.cpp`.

### Compiling the code

The script can be compiled with issuing the `make` command in the `src`
directory. There are two caveats:

- currently only `g++` is supported
- `g++` version of at least 8 is required for C++17 support
