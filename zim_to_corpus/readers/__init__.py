#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
import gzip
from itertools import count
import struct
from typing import Callable, Generator

from bs4 import BeautifulSoup

from .simple_html import parse as parse_simple_html  # noqa
from .zim_gutenberg import parse as parse_gutenberg
from .zim_wiki import parse as parse_zim_wiki


def enumerate_static_dump(static_dump_file: str) -> Generator[str, None, None]:
    """
    Reads the specified static HTML dump file (the output of
    :command:`zim_to_dir`) and enumerates all pages therein.
    """
    with gzip.open(static_dump_file, 'rb') as inf:
        for doc_no in count(1):
            size_raw = inf.read(4)
            if not size_raw:
                break
            elif len(size_raw) != 4:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            size = struct.unpack('!i', size_raw)[0]
            html_raw = inf.read(size)
            if len(html_raw) != size:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            html = html_raw.decode('utf-8')
            yield html


class Parser(Enum):
    """Enum for name -> parse function mapping."""
    WIKIPEDIA = (parse_zim_wiki, 'Wikipedia')
    GUTENBERG = (parse_gutenberg, 'Project Gutenberg')
    WP = WIKIPEDIA
    PG = GUTENBERG

    def __init__(self, parse: Callable[[str], BeautifulSoup], canonical: str):
        """Two members: the parser function and the canonical name."""
        self.parse = parse
        self.canonical = canonical


def get_parser(data_type: str) -> Parser:
    """Returns the parser enum for _data_type_."""
    try:
        return getattr(Parser, data_type.upper())
    except AttributeError:
        raise ValueError(f'No data_type {data_type}. Try one of '
                         f'{[c.canonical for c in Parser]}.')
