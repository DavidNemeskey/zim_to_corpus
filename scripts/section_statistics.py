#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Collects the (top-level) sections in the Wikipedia corpus and the ratio of
them being empty aside from a list.
"""

from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import dataclass
import gzip
import json
import logging
from multiprocessing import Pool
import os
import os.path as op
from typing import Dict

from bs4.element import Tag
from multiprocessing_logging import install_mp_handler

from zim_to_corpus.readers import parse_simple_html
from zim_to_corpus.transformations import remove_tags
from zim_to_corpus.html import headerp


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', '-i', required=True,
                        help='the input directory.')
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
    return args


@dataclass
class Statistics:
    """Section statistics."""
    # The number we see it
    count: int = 0
    # The number of times we see the section as empty if lists are removed
    empty: int = 0
    # Sum of the distance from the last section
    position: int = 0

    def __iadd__(self, other):
        self.count += other.count
        self.empty += other.empty
        self.position += other.position
        return self

    def __repr__(self):
        empty_ratio = self.empty / self.count if self.count else 0
        pos_ratio = self.position / self.count if self.count else 0
        return (f'{self.count}\t{self.empty}\t{empty_ratio}\t'
                f'{self.position}\t{pos_ratio}')


def get_title(section: Tag) -> str:
    """Returns the title of the section."""
    for child in section.children:
        if headerp.match(child.name):
            return child.get_text()
    else:
        raise ValueError('No header in section')


def statistics(input_file: str) -> Dict[str, Statistics]:
    section_stats = defaultdict(Statistics)
    with gzip.open(input_file) as inf:
        for doc_no, line in enumerate(inf, start=1):
            html = parse_simple_html(json.loads(line))
            sections = [c for c in html.body.children
                        if isinstance(c, Tag)]
            all_sections = set()

            for i, section in enumerate(sections, start=1):
                try:
                    title = get_title(section)
                    all_sections.add(title)
                    stats = section_stats[title]
                    stats.count += 1
                    stats.position += len(sections) - i
                except ValueError:
                    logging.error(f'No header for section {i} in '
                                  f'{html.head.title.get_text()}')

            remove_tags(html, {'ol', 'ul'})
            nonempty_sections = set()
            for section in (c for c in html.body.children if isinstance(c, Tag)):
                try:
                    title = get_title(section)
                    nonempty_sections.add(title)
                except ValueError:
                    pass

            for title in all_sections - nonempty_sections:
                section_stats[title].empty += 1

    return section_stats


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    install_mp_handler()

    input_files = [op.join(args.input_dir, f) for f in
                   os.listdir(args.input_dir)]

    logging.info(f'Scheduled {len(input_files)} files.')

    with Pool(args.processes) as pool:
        all_stats = defaultdict(Statistics)
        for section_stats in pool.imap_unordered(statistics, input_files):
            for title, stats in section_stats.items():
                all_stats[title] += stats

    for title, stats in sorted(all_stats.items()):
        print(f'{title}\t{stats}')

    logging.info(f'Done. Collected statistics for {len(all_stats)} sections.')


if __name__ == '__main__':
    main()