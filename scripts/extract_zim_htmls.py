#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extracts all Wikipedia HTMLs from the files output by zim_to_dir. Each
Wikipedia page is filtered and converted into a minimal HTML, and then saved
as a JSON string. In theory, this step could have been
skipped, and the script that creates the final format(s) could have operated on
the output of zim_to_dir. However, filtering substantially decreases the size
of, and access time to, the data. This factor becomes important, as there are
several output formats and the converter script might be called for all of them.
Finally, the JSON-per-line format is ubiquitous, while the output of zim_to_dir
is not.
"""

from argparse import ArgumentParser
from gzip import open as gopen
from io import StringIO
import json
import logging
from multiprocessing import Pool
import os
import os.path as op
import struct

from multiprocessing_logging import install_mp_handler

from zim_to_corpus.wiki import parse_zim_html


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
    parser.add_argument('--output-dir', '-o', required=True,
                        help='the output directory.')
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


def convert_to_json(input_file: str, output_file: str) -> int:
    """
    Parses all Wikipedia pages in _input_file_ and writes them to in a simple
    HTML format to _output_file_ as one JSON string per line.

    :returns: the number of documents converted.
    """
    logging.debug(f'Converting {input_file} to {output_file}...')
    doc_no = 0
    try:
        with gopen(input_file, 'rb') as inf, gopen(output_file, 'wt') as outf:
            while True:
                size_raw = inf.read(4)
                if len(size_raw) != 4:
                    raise EOFError()
                elif not size_raw:
                    break
                size = struct.unpack('!i', size_raw)[0]
                html_raw = inf.read(size)
                if len(html_raw) != size:
                    raise EOFError()
                html = html_raw.decode('utf-8')
                doc_no += 1
                wp = parse_zim_html(html)
                sio = StringIO()
                wp.to_html(sio)
                print(json.dumps(sio.getvalue()), file=outf)
    except EOFError:
        logging.error(f'{input_file} ended abruptly after {doc_no} documents.')
        return doc_no

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

    in_out_files = [(op.join(args.input_dir, f), op.join(args.output_dir, f))
                    for f in os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(in_out_files)} files for conversion.')

    with Pool(args.processes) as pool:
        total_docs = sum(pool.starmap(convert_to_json, in_out_files))

    logging.info(f'Done. Converted a total of {total_docs} documents.')


if __name__ == '__main__':
    main()
