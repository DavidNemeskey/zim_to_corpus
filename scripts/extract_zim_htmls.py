#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extracts all (Wikipedia, Project Gutenberg) HTMLs from the files output by
zim_to_dir. Each page is cleaned up, filtered and converted into a minimal
HTML, and then saved as a JSON string. In theory, this step could have been
skipped, and the script that creates the final format(s) could have operated on
the output of zim_to_dir. However, filtering substantially decreases the size
of, and access time to, the data. This factor becomes important, as there are
several output formats and the converter script might be called for all of them.
Finally, the JSON-per-line format is ubiquitous, while the output of zim_to_dir
is not.
"""

import zim_to_corpus.istarmap  # noqa

from argparse import ArgumentParser
from functools import partial
import gzip
import json
import logging
from multiprocessing import Pool
import os
import os.path as op
import sys
from typing import Dict

from bs4 import BeautifulSoup
# from multiprocessing_logging import install_mp_handler
from tqdm import tqdm

from zim_to_corpus.readers import (
    enumerate_static_dump, get_parser, normalize_text, Parser
)
from zim_to_corpus.transformations import remove_empty_tags
from zim_to_corpus.utils import parse_json


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
    parser.add_argument('--output-dir', '-o', required=True,
                        help='the output directory.')
    parser.add_argument('--type', '-t', required=True,
                        choices=[p.name.lower() for p in Parser],
                        help='the type of content to extract: '
                             'Wikipedia or Project Gutenberg.')
    parser.add_argument('--type-parameters', '-p',
                        type=partial(parse_json, arg='-p'),
                        help='supply extra parameters to the parser type (-t) '
                             'in a JSON dictionary. For the list of '
                             'parameters available, check the readers in '
                             'package zim_to_corpus.readers.')
    parser.add_argument('--processes', '-P', type=int, default=1,
                        help='number of worker processes to use (max is the '
                             'num of cores, default: 1)')
    parser.add_argument('--log-level', '-L', type=str, default='info',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='the logging level.')
    args = parser.parse_args()

    num_procs = len(os.sched_getaffinity(0))
    if args.processes < 1 or args.processes > num_procs:
        parser.error('Number of processes must be between 1 and {}'.format(
            num_procs))
    return args


def convert_to_json(input_file: str, output_file: str, data_type: str,
                    parser_args: Dict) -> int:
    """
    Parses all pages in _input_file_ and writes them to in a simple
    HTML format to _output_file_ as one JSON string per line.

    :param data_type: the type of the content to parse (Wikipedia, ...)
    :returns: the number of documents converted.
    """
    logging.info(f'Converting {input_file} to {output_file}...')
    parsed_docs = 0
    try:
        with gzip.open(output_file, 'wt') as outf:
            for doc_no, html in enumerate(enumerate_static_dump(input_file), 1):
                doc = get_parser(data_type).parse(html, **parser_args)
                # Only keep non-empty (e.g. not-all-image) pages
                remove_empty_tags(doc)
                if doc.find('body'):
                    # print(json.dumps(doc.prettify()), file=outf)
                    # We re-parse the HTML so that if BeautifulSoup does any
                    # modifications (such as deleting superfluous newlines),
                    # it does it NOW. In this case, if anyone reparses
                    # our output and changes it, diff will still work and
                    # not report a lot of (potential) cosmetic changes.
                    clean_text = normalize_text(str(doc))
                    print(json.dumps(str(BeautifulSoup(clean_text))), file=outf)
                    parsed_docs += 1
                else:
                    title_tag = doc.find('title')
                    title = title_tag.get_text() if title_tag else '<no title>'
                    logging.info(f'No body in document {doc_no}: {title}')
    except EOFError as ee:
        logging.error(ee)
        return doc_no
    except:
        logging.exception(f'Error in {input_file}, document {doc_no}.')
        raise

    logging.info(f'Converted {parsed_docs} documents from '
                 f'{input_file} to {output_file}.')
    return doc_no


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    # Note: multiprocessing_logging sometimes causes hangups. In that case,
    #       just comment out these logging statements, as well as
    #       instal_mp_handler
    # install_mp_handler()

    logging.info(f'Script: {__file__}, args: {args}')

    os.nice(20)
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)

    in_out_files = [(op.join(args.input_dir, f), op.join(args.output_dir, f))
                    for f in os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(in_out_files)} '
                 f'{get_parser(args.type).canonical} files for conversion.')

    parser_args = args.type_parameters or {}
    with Pool(args.processes) as pool:
        f = partial(convert_to_json,
                    data_type=args.type, parser_args=parser_args)
        progress_bar = partial(tqdm, total=len(in_out_files), file=sys.stdout)
        total_docs = sum(progress_bar(pool.istarmap(f, in_out_files)))

        pool.close()
        pool.join()

    logging.info(f'Done. Converted a total of {total_docs} documents.')


if __name__ == '__main__':
    main()
