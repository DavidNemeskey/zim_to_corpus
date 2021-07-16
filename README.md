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
directory. There are a few caveats.

#### Compiler

Currently only `g++` is supported and at least version 8 is required for
proper C++17 support.

#### Libraries

The program requires a few libraries to work. Three of these (`cxxopts`,
`zstr` and `spdlog`) are added as submodule to this repository. Make sure to
clone it recursively (i.e.

```
git clone --recursive https://github.com/DavidNemeskey/zim_to_corpus
```

) or to activate the submodules after cloning normally:

```
git submodule init
git submodule update
```

Aside from these, two other libraries (and their sources or `-dev` packages) are  required:

- [`libzim`](https://github.com/openzim/libzim) (also called Zimlib) to process
  the files. Libzim can be installed from the repositories of Linux
  distributions (`libzim-dev`), or compiled from source;
- `zlib`, for compression (e.g. `zlib1g-dev` in Ubuntu).

Note that some of the files in the Kiwix archives (most importantly, the
English WP dump) require a recent version of libzim. A libzim version between
4.0 and 6.3 is recommended; note that the API changed in 7.0, and
`zim_to_dir` is not yet compatible with it. The version in recent Ubuntu
releases should work without problems.

### Troubleshooting

#### Compilation fails because of `article_index_type` not found

You have an older version of libzim. Either upgrade it to version 4 or newer,
or compile the code with `-DARTICLE_SIZE_TYPE`.

#### Invalid zim-file header

If `zim_to_dir` fails to read a zim file with the message
"_error reading zim-file header_", then it was compiled against an outdated
libzim version. Upgrade libzim to a more recent one.
against is 
