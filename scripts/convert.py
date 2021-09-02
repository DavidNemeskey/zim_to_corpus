#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converts documents (Wikipedia pages, Project Gutenberg books, etc.) in the
"simple HTML" format (i.e. the output of extract_zim_htmls.py) to various
other formats (WT-2, BERT, CoNLL-U tsv, etc.)
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
from typing import Any, Dict, List, Pattern, Set

from bs4 import BeautifulSoup
# from multiprocessing_logging import install_mp_handler
import regex as re
from tqdm import tqdm

from zim_to_corpus.html import get_html_title, get_section_title, html_template
from zim_to_corpus.readers import parse_simple_html
from zim_to_corpus.utils import (
    get_subclasses_of, identity, instantiate, parse_json, prefix_name
)
from zim_to_corpus.transformations import remove_empty_tags


def parse_arguments():
    converters = get_subclasses_of('Converter', 'zim_to_corpus.converters')
    tokenizers = get_subclasses_of('Tokenizer', 'zim_to_corpus.tokenization')

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
    parser.add_argument('--output-dir', '-o', required=True,
                        help='the output directory.')
    parser.add_argument('--unit', '-u', default='doc',
                        choices=['doc', 'document', 'section'],
                        help='the unit that should be converted to a single '
                             'output document. Depends on the data set; for '
                             'Wikipedia, document is the natural choice; for '
                             'Project Gutenberg books, section might be more '
                             'appropriate.')
    parser.add_argument('--uncased', '-c', action='store_true',
                        help='lowercase the text.')
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
    tok_group.add_argument('--tokenizer', '-t', default='whitespace',
                           help='the tokenizer to use for conversion. The '
                                'format of this tag is <tokenizer>:<param>. '
                                'The valid values for <tokenizer> are '
                                f'{{{", ".join(tokenizers.keys())}}}. The '
                                'parameter for qun(token) is the path to the '
                                'library; for spacy the model name. The default'
                                ' is the whitespace tokenizer.')
    tok_group.add_argument('--tokenizer-json', '-T',
                           type=partial(parse_json, arg='-T'),
                           help='instantiate the tokenizer via a JSON '
                                'dictionary; see -F, above. Only subclasses of '
                                'Tokenizer in the module tokenization are '
                                'supported.')
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

    return args


def sections_to_docs(html: BeautifulSoup) -> List[BeautifulSoup]:
    """Converts a single HTML document to a list of per-section documents."""
    ret = []
    for section_id, section in enumerate(html.find_all('section'), 1):
        bs = BeautifulSoup(html_template)
        try:
            ret.append(bs)
            bs.html.body.append(section)
            bs.html.head.title.append(get_section_title(section))
        except ValueError:
            logging.debug(f'No section title for section {section_id} '
                          f'in {get_html_title(html)}')
    return ret


def uncase(text):
    """"Uncases" (lowercases) _text_."""
    # TODO delete if not needed
    return text.lower()


def convert(input_file: str, output_dir: str, section_as_doc: bool,
            format_args: Dict[str, Any],
            tokenizer_args: Dict[str, Any],
            uncased: bool = False) -> int:
    """
    Parses all documents in _input_file_ and writes them to a file in
    _output_dir in the specified format. The file name of the new file will
    be the same as _input_file_, with the exception of the extension, which
    will reflect the output format.

    :returns: the number of documents converted.
    """
    case = str.lower if uncased else identity
    tokenizer = instantiate(**tokenizer_args)
    format_args.setdefault('args', []).insert(0, tokenizer)
    converter = instantiate(**format_args)
    output_file = op.join(
        output_dir,
        op.basename(input_file).replace('htmls',
                                        prefix_name(converter.__class__))
    )

    logging.info(f'Converting {input_file} to {output_file}...')
    # For deleting control characters from the HTML text...
    del_ctrl = re.compile(r'[\p{C}--\t\n]', re.V1)
    # ... and replacing tabs with spaces
    repl_sep = re.compile(r'[\p{Z}\t]', re.V1)
    with gzip.open(input_file) as inf, gzip.open(output_file, 'wt') as outf:
        header = converter.header()
        if header:
            print(header, file=outf)
        for doc_no, line in enumerate(inf, start=1):
            html = None
            try:
                raw_html = json.loads(line)
                clean_html = repl_sep.sub('    ', del_ctrl.sub('', raw_html))
                html = parse_simple_html(clean_html)
                title = get_html_title(html)

                # Just to be on the safe side
                remove_empty_tags(html)

                # We are done, let's print the document!
                if section_as_doc:
                    for section_doc in sections_to_docs(html):
                        print(case(converter(section_doc)),
                              file=outf, end='')
                else:
                    print(case(converter(html)), file=outf, end='')
            except:
                html_text = f'in {title} ' if html and title else ''
                logging.exception(f'Something happened {html_text} in file '
                                  f'{input_file}, line {doc_no}.')
    logging.info(f'Converted {doc_no} documents from '
                 f'{input_file} to {output_file}.')
    return doc_no


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
        with open(file_name, 'rt') as inf:
            return re.compile(
                '|'.join((re.escape(line.strip()) for line in inf)))
    else:
        return None


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    # install_mp_handler()

    logging.info(f'Script: {__file__}, args: {args}')

    os.nice(20)
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)

    input_files = [op.join(args.input_dir, f) for f in
                   os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(input_files)} files for conversion.')

    with Pool(args.processes) as pool:
        f = partial(convert, output_dir=args.output_dir,
                    section_as_doc=args.unit == 'section',
                    format_args=args.format_json,
                    tokenizer_args=args.tokenizer_json,
                    uncased=args.uncased)
        progress_bar = partial(tqdm, total=len(input_files), file=sys.stdout)
        total_docs = sum(progress_bar(pool.imap_unordered(f, input_files)))
        pool.close()
        pool.join()

    logging.info(f'Done. Converted a total of {total_docs} documents.')


if __name__ == '__main__':
    main()
