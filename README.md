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
- Building the docker image from the `Dockerfile` in the `docker` directory
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
records can be increased (from 4) to speed it up somewhat. However, since the
`zim` format is sequential, the whole task is, to a large extent, I/O bound;
because of this, the speed tops at a certain number of threads depending on the
storage type: slow HDDs max out around 4 threads, while fast SSDs can scale
even up to 24.

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
build the docker image, which compiles the source and all its dependencies:

```
cd docker
docker build -t zim_to_dir .
```

This method has the added benefit of not polluting the system with potentially
unneeded libraries and packages and it also works without `root` access.

For those who wish to compile the code manually, here we present the general
guidelines. Check out the `Dockerfile` for the detailed list of commands.

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

## `extract_zim_htmls.py`

Extracts all (Wikipedia, Project Gutenberg) HTMLs from the files output by
`zim_to_dir`. Each page is cleaned up, filtered and converted into a minimal
HTML, and then saved as a JSON string. In theory, this step could have been
skipped, and the script that creates the final format(s) could have operated on
the output of zim_to_dir. However, filtering substantially decreases the size
of, and access time to, the data. This factor becomes important, as there are
several output formats and the converter script might be called for all of
them.  Finally, the JSON-per-line format is ubiquitous, while the output of
`zim_to_dir` is not.

Example usage converting the Wikipedia pages to simple HTML, retaining links
and converting mathematical formulas to a placeholder symbol:

```
extract_zim_htmls.py -i hu_mini -o hu_json_htmls -t wikipedia -p '{"retain_tags": {"a": true}, "tag_replacements": {"math": "$MATH$"}, "delete_footnotes": true}' -P 4
```

## `filter_htmls.py`

Filters documents and sections from the output of `extract_zim_htmls.py`. Also
has an option to filter documents which fall below a certain character count
after section removal.

Example usage:

```
filter_htmls.py -i hu_json_htmls -o hu_filtered_htmls -s skip_sections.lst -S skip_sections.regex -P 4
```
, where
- `skip_sections.regex` contains one regex per line, such as `^Source`, `.* reading$`
- `skip_sections.lst` contains full section names on a line such as `Notes`

See `section_statistics.py`, below.

## `convert.py`

Converts documents (Wikipedia pages, Project Gutenberg books, etc.) in the
"simple HTML" format (i.e. the output of `extract_zim_htmls.py`) to various
other formats (WT-2, BERT, CoNLL-U tsv, etc.)

Various output formats are supported, each of which has its own set parameters.
The same can be said of the supported tokenizers. The available parameters can
be found in the `zim_to_corpus.converters` module and
`zim_to_corpus.tokenization` package.

Usage example with converting the filtered htmls to tsv, tokenized with
[emtsv](https://github.com/nytud/emtsv):

```
convert.py -i hu_filtered_htmls -o hu_tokenized_tsvs -u doc -f tsv -t "qun:http://localhost:5000" -P 4
```

**Note** that the paragraphs are sent to the tokenizers one-by-one. The
tokenizer in `emtsv` exhibits abysmal performance in this use-case, taking
more than a second to process a single page. Use with caution.

## `section_statistics.py`

Collects statistics of each section title in the corpus. The output is a `tsv`
file with the following columns:
- section title
- number of times it occurs in the corpus
- the number of times it is "empty", i.e. it only contains lists
- the "_empty ratio_": the quotient of the last two numbers
- the sum of the positions of the section, counted from the read $--$
  probably not a very useful metric
- the _average position_ of the section, counted from the rear. Sections such as
  _Sources_ or _References_ have typically a low average position

The resulting statistics can be used to generate section filtering lists for
`filter_htmls.py`.
