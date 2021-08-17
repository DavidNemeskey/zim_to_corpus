#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Filters documents or their sections in the simple HTML format
(in other words: after ``extract_zim_htmls.py``, but before ``convert.py``).
"""

from argparse import ArgumentParser
from functools import partial
import gzip
import json
import logging
from multiprocessing import Pool
import os
import os.path as op
import sys
from typing import Pattern, Set, Tuple

from multiprocessing_logging import install_mp_handler
import regex as re
from tqdm import tqdm

from zim_to_corpus.html import get_html_title
from zim_to_corpus.readers import parse_simple_html
from zim_to_corpus.transformations import remove_empty_tags, remove_sections


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
    parser.add_argument('--output-dir', '-o', required=True,
                        help='the output directory.')
    parser.add_argument('--filter-sections', '-s',
                        help='a file that lists sections (headers thereof) '
                             'that should be removed from the pages before '
                             'conversion. The file should list one title each '
                             'line.')
    parser.add_argument('--filter-sections-by-regex', '-S',
                        help='a file that lists regular expressions, one per '
                             'line. Sections whose header matches one of them '
                             'are removed from the pages before conversion.')
    parser.add_argument('--filter-documents', '-d',
                        help='a file that lists regular expression patterns '
                             'for titles of documents to skip. Some documents '
                             'might turn out to be useless, contain content '
                             'that breaks the tokenizer, etc.')
    parser.add_argument('--processes', '-P', type=int, default=1,
                        help='number of worker processes to use (max is the '
                             'num of cores, default: 1)')
    parser.add_argument('--log-level', '-L', type=str, default='info',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='the logging level.')
    args = parser.parse_args()

    num_procs = len(os.sched_getaffinity(0))
    if args.processes < 1 or args.processes > num_procs:
        parser.error(f'Number of processes must be between 1 and {num_procs}')
    if not (
        args.filter_sections or args.filter_sections_by_regex or
        args.filter_documents
    ):
        parser.error('At least one filtering option (-s, -S, -d) '
                     'must be specified.')
    return args


def file_to_set(file_name: str) -> Set[str]:
    """
    Loads a file to a set.

    :returns: the lines of the file in a ``set``, an empty ``set`` if
              _file_name_ is ``None``.
    """
    if file_name:
        with open(file_name, 'rt') as inf:
            set_from_file = set(line.strip() for line in inf)
    else:
        set_from_file = set()
    return set_from_file


def file_to_regex(file_name: str) -> Pattern:
    """
    Loads a file to a regex. Lines are "disjuncted".

    :returns: a regex that is the disjunction of all lines in the file, or
              ``None`` if _file_name_ is.
    """
    if file_name:
        return re.compile(
            '|'.join((f'({p})' for p in file_to_set(file_name))),
            re.V0 | re.I
        )
    else:
        return None


def filter_file(input_file: str, output_dir: str,
                sections_to_filter: Set[str],
                sections_to_filter_regex: Pattern,
                documents_to_filter: Set[Pattern]) -> Tuple[int, int]:
    """
    Filters sections and documents from _intput_file_ and writes the rest
    to _output_file_. Returns the number of documents read and written as
    a 2-tuple.
    """
    output_file = op.join(output_dir, op.basename(input_file))
    logging.info(f'Filtering {input_file} to {output_file}...')

    written = 0
    with gzip.open(input_file) as inf, gzip.open(output_file, 'wt') as outf:
        for doc_no, line in enumerate(inf, start=1):
            html = None
            try:
                raw_html = json.loads(line)
                html = parse_simple_html(raw_html)
                title = get_html_title(html)
                if (
                    title and documents_to_filter and
                    documents_to_filter.search(title)
                ):
                    logging.debug(f'Skipping document {title}...')
                    continue
                if sections_to_filter or sections_to_filter_regex:
                    remove_sections(html,
                                    sections_to_filter,
                                    sections_to_filter_regex)

                # As a last step, let's get rid of the empty tags now
                remove_empty_tags(html)

                if html.find('body'):
                    print(json.dumps(str(html)), file=outf)
                    written += 1
            except:
                html_text = f'in {title} ' if html and title else ''
                logging.exception(f'Something happened {html_text} in file '
                                  f'{input_file}, line {doc_no}.')
    logging.info(f'Filtered {doc_no - written} documents from '
                 f'{input_file}; kept {written}.')
    return doc_no, written


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    install_mp_handler()

    logging.info(f'Script: {__file__}, args: {args}')

    os.nice(20)
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)

    input_files = [op.join(args.input_dir, f) for f in
                   os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(input_files)} files for filtering.')

    sections_to_filter = file_to_set(args.filter_sections)
    sections_to_filter_regex = file_to_regex(args.filter_sections_by_regex)
    documents_to_filter = file_to_regex(args.filter_documents)

    if sections_to_filter:
        logging.info(f'Filtering {len(sections_to_filter)} exact sections.')
    if sections_to_filter_regex:
        logging.info(
            f'Filtering {sections_to_filter_regex.pattern.count("|") + 1} '
            'patterns.'
        )
    if documents_to_filter:
        logging.info(f'Filtering {documents_to_filter.pattern.count("|") + 1} '
                     'document patterns.')

    with Pool(args.processes) as pool:
        f = partial(filter_file, output_dir=args.output_dir,
                    sections_to_filter=sections_to_filter,
                    sections_to_filter_regex=sections_to_filter_regex,
                    documents_to_filter=documents_to_filter)
        progress_bar = partial(tqdm, total=len(input_files), file=sys.stdout)
        docs_read, docs_written = 0, 0
        for read, written in progress_bar(pool.imap_unordered(f, input_files)):
            docs_read += read
            docs_written += written
        pool.close()
        pool.join()

    logging.info(f'Done. Filtered a total of {docs_read} documents, '
                 f'keeping {docs_written}.')


if __name__ == '__main__':
    main()
