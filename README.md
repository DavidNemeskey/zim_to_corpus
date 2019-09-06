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

### Libraries

The program requires two libraries to work:

- [`libzim`](https://github.com/openzim/libzim) (also called Zimlib) to process
  the files. Libzim can be installed from the repositories of Linux
  distributions, or compiled from source;
- `zlib`, for compression.

Note that some of the files in the Kiwix archives (most importantly, the
English WP dump) require a recent version of libzim. For instance, the
`libzim0v5` version found in Ubuntu Xenial / Linux Mint 18 fails with
"_error reading zim-file header_". Because of this, libzim version 4.0.0+ is
recommended.

### Troubleshooting

#### Compilation fails because of `article_index_type` not found

You have an older version of libzim. Either upgrade it to version 4 or newer,
or compile the code with `-DARTICLE_SIZE_TYPE`.

#### Invalid zim-file header

If `zim_to_dir` fails to read a zim file with the message
"_error reading zim-file header_", then it was compiled against an outdated
libzim version. Upgrade libzim to a more recent one.
against is 
