# zim_to_corpus

Scripts to extract the text from (mostly) Wikipedia pages from .zim archives.
The repository contains two components: `zim_to_dir`, a C++ program to extract
pages from zim archives; and a number of Python scripts to process its output
and convert the data into various formats (such as inputs for BERT, fasttext,
etc).

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

### How to acquire

The `zim_to_dir` executable can be acquired in several ways:
- Downloading a release from
  [the `zim_to_corpus` repository](https://github.com/DavidNemeskey/zim_to_corpus)
- Using the docker image, either by downloading it from the Docker Hub or
  building it from the `Dockerfile` in the `docker` directory
- Compiling the code manually

### Usage

#### The executable

The executable has two main arguments: `-i` is used to specify the input `.zim`
file, and `-o` the output directory. The rest of the arguments can be used to
tune some of the aspects of the process; use the `-h/--help` option to list
them. An example run:

```
zim_to_dir -i wikipedia_hu_all_mini.zim -o hu_mini/ -d 2000
```

One thing worth mentioning: the number of threads the program uses to parse
records can be increased to speed it up somewhat. However, since the `zim`
format is inherently sequential, the speed tops at around 4 threads (might
depend on the storage).

#### Docker image

The docker image can be used in two ways:
1. The `zim_to_dir` executable can be copied out of a container and used
as described above. For instance:
```
$ docker create zim_to_dir
e892d6ff245b55e03e41384d1e7d2838babd944a8e31096b3677a05359f38aba
$ docker cp e892d6ff245b:/zim_to_dir .
$ docker rm e892d6ff245b
e892d6ff245b
```
2. The container is also runnable and will run `zim_to_dir` by default. However,
in order for the container to see the input and output directories, they must
be mounted as volumes:
```
docker run --rm --mount type=bind,source=/home/user/data/,target=/data zim_to_dir -i /data/wikipedia_hu_all_mini.zim -o /data/hu_mini/ -d 2000
```

### Compiling the code

The script can be compiled with issuing the `make` command in the `src`
directory. There are a few caveats, and because of this, it is easier to 
build the docker image, which compiles the source and all its dependencies.
Here we present the general guidelines; check out the `Dockerfile` for the
details.

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

1. `zlib`, for compression (e.g. `zlib1g-dev` in Ubuntu);
2. [`libzim`](https://github.com/openzim/libzim) (also called Zimlib) to
   process the files. Libzim can be installed from the repositories of Linux
   distributions (`libzim-dev`), but e.g. Ubuntu only has version 4, so
   depending on how recent is the file to process, it might have to be
   compiled [from source](https://github.com/openzim/libzim).

Note that some of the files in the Kiwix archives (most importantly, the
English WP dump) require a fresh version of libzim. libzim version
6.3 is recommended; note that the API changed in 7.0, and
`zim_to_dir` is not yet compatible with it.

### Troubleshooting

#### Compilation fails because of `article_index_type` not found

You have an older version of libzim. Either upgrade it to version 4 or newer,
or compile the code with `-DARTICLE_SIZE_TYPE`.

#### Invalid zim-file header

If `zim_to_dir` fails to read a zim file with the message
"_error reading zim-file header_", then it was compiled against an outdated
libzim version. Upgrade libzim to a more recent one.
against is 
