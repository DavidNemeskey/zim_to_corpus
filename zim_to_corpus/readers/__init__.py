#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
import gzip
from itertools import count
import struct
from typing import Callable, Generator

from bs4 import BeautifulSoup
import regex as re

from .simple_html import parse as parse_simple_html  # noqa
from .zim_gutenberg import parse as parse_gutenberg
from .zim_wiki import parse as parse_zim_wiki


def enumerate_static_dump(static_dump_file: str) -> Generator[bytes, None, None]:
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
            # Unfortunately pages are not necessarily in UTF-8
            yield html_raw


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


# For deleting control characters from the HTML text...
del_ctrl = re.compile(r'[\p{C}--\t\n]', re.V1)
# ... and replacing tabs and other whitespaces with spaces
repl_sep = re.compile(r'[\p{Z}]', re.V1)
repl_tab = re.compile(r'\t', re.V0)


def normalize_text(text: str) -> str:
    """
    Cleans the text: removes control characters, normalizes whitespaces, etc.
    """
    clean_text = del_ctrl.sub('', text)
    clean_text = repl_sep.sub(' ', repl_tab.sub('    ', clean_text))
    return clean_text
