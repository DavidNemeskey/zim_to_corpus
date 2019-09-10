#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that convert from the canonical "simple HTML" format to various
other formats.
"""

from io import StringIO
import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.html import headerp, listp


class WT2Converter:
    def __init__(self, bullet: str = None, indent: int = 0):
        self.bullet = f' {bullet}' if bullet else ''
        self.indent = ' ' * indent

    def convert_li(self, li: Tag, out: StringIO, level: int):
        for child in li:
            # There should be only one
            if isinstance(child, NavigableString):
                print(f'{self.indent * level}{self.bullet} {child}', file=out)
            elif self.listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')

    def convert_list(self, lst: Tag, out: StringIO, level: int = 0):
        for child in lst:
            if child.name == 'li':
                self.convert_li(child, out, level)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list')

    def convert_section(self, section: Tag, out: StringIO):
        for child in section.children:
            if self.headerp.match(child.name):
                mustache = ' '.join('=' * int(child.name[1:]))
                print(f'\n {mustache} {child.get_text()} {mustache} \n', file=out)
            elif self.listp.match(child.name):
                self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            elif child.name == 'p':
                print(f' {child.get_text()} ', file=out)
            else:
                raise ValueError(f'Unexpected tag {child.name} in section')

    def __call__(self, html: BeautifulSoup, list_bullets=False) -> str:
        """
        Converts _html_ to WT-2- (WikiText-2-) format, with some variations allowed.

        :param html: the minimal HTML representation of a Wikipedia page.
        :param list_bullets: have bullets (and numbers) for lists. The default is
                             ``False`` to comply with the original WT-2 format.
        :returns: the WT-2 text representation of _html_.
        """
        out = StringIO()
        for section in (c for c in html.find('body').children if isinstance(c, Tag)):
            self.convert_section(section, out)
        print(file=out)
        return out.getvalue()
