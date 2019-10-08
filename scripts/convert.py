#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converts documents (Wikipedia pages, Project Gutenberg books, etc.) in the
"simple HTML" format (i.e. the output of convert.py) to various other formats
(WT-2, BERT, CoNLL-U tsv, etc.)
"""

from argparse import ArgumentParser
from functools import partial
import gzip
import json
import logging
from multiprocessing import Pool
import os
import os.path as op
from typing import Any, Dict, Set

from multiprocessing_logging import install_mp_handler

from zim_to_corpus.readers import parse_simple_html
from zim_to_corpus.utils import (
    get_subclasses_of, instantiate, parse_json, prefix_name
)
from zim_to_corpus.transformations import remove_sections


def parse_arguments():
    converters = get_subclasses_of('Converter', 'zim_to_corpus.converters')
    tokenizers = get_subclasses_of('Tokenizer', 'zim_to_corpus.tokenization')

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
    parser.add_argument('--output-dir', '-o', required=True,
                        help='the output directory.')
    form_group = parser.add_mutually_exclusive_group(required=True)
    form_group.add_argument('--format', '-f', choices=sorted(converters.keys()),
                            help='the format to convert to.')
    form_group.add_argument('--format-json', '-F',
                            type=partial(parse_json, arg='-F'),
                            help='instantiate the formatter via a JSON '
                                 'dictionary. It supports the keys cls, '
                                 'args and kwargs, which are hopefully '
                                 'all self-explanatory (the tokenizer argument '
                                 'should be omitted). Only subclasses of '
                                 'Converter in the module converters are '
                                 'supported.')
    tok_group = parser.add_mutually_exclusive_group()
    tok_group.add_argument('--tokenizer', '-t', default='dummy',
                           help='the tokenizer to use for conversion. The '
                                'format of this tag is <tokenizer>:<param>. '
                                'The valid values for <tokenizer> are '
                                f'{{{", ".join(tokenizers.keys())}}}. The '
                                'parameter for qun(token) is the path to the '
                                'library; for spacy the model name. The default'
                                ' is the dummy tokenizer, which does nothing.')
    tok_group.add_argument('--tokenizer-json', '-T',
                           type=partial(parse_json, arg='-T'),
                           help='instantiate the tokenizer via a JSON '
                                'dictionary; see -F, above. Only subclasses of '
                                'Tokenizer in the module tokenization are '
                                'supported.')
    parser.add_argument('--filter-sections', '-s',
                        help='a file that lists sections (headers thereof) '
                             'that should be removed from the pages before '
                             'conversion. The file should list one title each '
                             'line.')
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

    if args.format:
        args.format_json = {
            'cls': get_subclasses_of(
                'Converter', 'zim_to_corpus.converters')[args.format].__name__,
        }
    args.format_json['module'] = 'zim_to_corpus.converters'
    try:
        if args.tokenizer:
            tok_name, _, param_str = args.tokenizer.partition(':')
            args.tokenizer_json = {
                'cls': tokenizers[tok_name].__name__,
            }
            if param_str:
                args.tokenizer_json['args'] = [param_str]
        args.tokenizer_json['module'] = 'zim_to_corpus.tokenization'
    except KeyError:
        parser.error(f'Valid tokenizers are {{{", ".join(tokenizers.keys())}}}')

    print(args)
    return args


def convert(input_file: str, output_dir: str,
            format_args: Dict[str, Any], tokenizer_args: Dict[str, Any],
            sections_to_filter: Set[str]) -> int:
    """
    Parses all documents in _input_file_ and writes them to a file in
    _output_dir in the specified format. The file name of the new file will
    be the same as _input_file_, with the exception of the extension, which
    will reflect the output format.

    :returns: the number of documents converted.
    """
    tokenizer = instantiate(**tokenizer_args)
    format_args.setdefault('args', []).insert(0, tokenizer)
    converter = instantiate(**format_args)
    output_file = op.join(
        output_dir,
        op.basename(input_file).replace('htmls',
                                        prefix_name(converter.__class__))
    )

    logging.debug(f'Converting {input_file} to {output_file}...')
    with gzip.open(input_file) as inf, gzip.open(output_file, 'wt') as outf:
        for doc_no, line in enumerate(inf, start=1):
            html = parse_simple_html(json.loads(line))
            if sections_to_filter:
                remove_sections(html, sections_to_filter)
            print(converter(html), file=outf)
    logging.debug(f'Converted {doc_no} documents from '
                  f'{input_file} to {output_file}.')
    return doc_no


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    install_mp_handler()

    os.nice(20)
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)

    input_files = [op.join(args.input_dir, f) for f in
                   os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(input_files)} files for conversion.')

    if args.filter_sections:
        with open(args.filter_section, 'rt') as inf:
            sections_to_filter = set(line.strip() for line in inf)
    else:
        sections_to_filter = None

    with Pool(args.processes) as pool:
        f = partial(convert, output_dir=args.output_dir,
                    format_args=args.format_json,
                    tokenizer_args=args.tokenizer_json,
                    sections_to_filter=sections_to_filter)
        total_docs = sum(pool.imap_unordered(f, input_files))

    logging.info(f'Done. Converted a total of {total_docs} documents.')


if __name__ == '__main__':
    main()
