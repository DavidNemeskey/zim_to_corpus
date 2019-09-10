#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that convert from the canonical "simple HTML" format to various
other formats.
"""

from io import StringIO

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.html import headerp, listp

class Converter:
    """Base class for all converters."""
    def __call__(self, html: BeautifulSoup) -> str:
        """
        Converts _html_ to text in a specific format.

        :param html: the minimal HTML representation of a Wikipedia page.
        :returns: the converted text.
        """
        out = StringIO()
        for section in (c for c in html.find('body').children if isinstance(c, Tag)):
            self.convert_section(section, out)
        return out.getvalue()

    def convert_list(self, lst: Tag, out: StringIO, level: int = 0):
        """
        Converts a list to text. The text is written to _out_.

        :param lst: the list tag.
        :param out: the :class:`StringIO` that collects the output.
        :param level: the embedding "level" of the list. Top-level lists have
                      _level_ ``0``, a list embedded into one _level_ ``1``,
                      etc.
        """
        position = 1
        for child in lst:
            if child.name == 'li':
                self.convert_li(child, out, level,
                                position if lst.name == 'ol' else 0)
                position += 1
            else:
                raise ValueError(f'Unexpected tag {child.name} in list')


# TODO tokenization
# TODO to corpus format
# TODO to markdown
# TODO section filtering
class WT2Converter(Converter):
    def __init__(self, bullet: str = None, indent: int = 0):
        """
        Creates a new :class:`WT2Converter`.

        :param bullet: the character to use as bullets for lists. The default is
                       ``None``, which means no list bullets (or numbers)
                       will be used. This complies with the original WT-2 format.
        :param indent: the number of spaces to indent a list embedded in another.
        """
        self.bullet = f' {bullet}' if bullet else ''
        self.indent = ' ' * indent

    def convert_section(self, section: Tag, out: StringIO):
        """
        Converts a section to text. The text is written to _out_.

        :param section: the section tag.
        :param out: the :class:`StringIO` that collects the output.
        """
        for child in section.children:
            if headerp.match(child.name):
                mustache = ' '.join('=' * int(child.name[1:]))
                print(f'\n {mustache} {child.get_text()} {mustache} \n', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            elif child.name == 'p':
                print(f' {child.get_text()} ', file=out)
            else:
                raise ValueError(f'Unexpected tag {child.name} in section')

    def convert_li(self, li: Tag, out: StringIO, level: int, index: int):
        """
        Converts a list item to text. The text is written to _out_.

        :param lst: the ``<li>`` tag.
        :param out: the :class:`StringIO` that collects the output.
        :param level: the embedding "level" of the list. Top-level lists have
                      _level_ ``0``, a list embedded into one _level_ ``1``,
                      etc.
        :param index: the position of the list item within the list. Needed
                      for ordered lists; ``0`` for unordered lists.
        """
        for child in li:
            # There should be only one
            if isinstance(child, NavigableString):
                # Need bullets / numbers
                if self.bullet:
                    bullet = f' {index}.' if index else self.bullet
                else:
                    bullet = ''
                print(f'{self.indent * level}{bullet} {child}', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')


class BERTConverter(Converter):
    def __init__(self, headers=False, lists=False,
                 bullet: str = None, indent: int = 0):
        """
        Creates a new :class:`BERTConverter`.

        .. note::
        Neither headers nor lists are preserved in the original BERT format.
        This class includes an option to keep them for experimental purposes.

        :param headers: whether headers should be included in the output.
        :param lists: whether lists should be included in the output.
        :param bullet: the character to use as bullets for lists. The default is
                       ``None``, which means no list bullets (or numbers)
                       will be used. This complies with the original WT-2 format.
        :param indent: the number of spaces to indent a list embedded in another.
        """
        self.headers = headers
        self.lists = lists
        self.bullet = f'{bullet} ' if bullet else ''
        self.indent = ' ' * indent

    def convert_section(self, section: Tag, out: StringIO):
        """
        Converts a section to text. The text is written to _out_.

        :param section: the section tag.
        :param out: the :class:`StringIO` that collects the output.
        """
        for child in section.children:
            if headerp.match(child.name):
                if self.headers:
                    print(child.get_text(), file=out)
            elif listp.match(child.name):
                if self.lists:
                    self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            elif child.name == 'p':
                for sentence in map(str.strip, child.get_text().split('\n')):
                    if sentence:
                        print(sentence, file=out)
            else:
                raise ValueError(f'Unexpected tag {child.name} in section')

    def convert_li(self, li: Tag, out: StringIO, level: int, index: int):
        """
        Converts a list item to text. The text is written to _out_.

        :param lst: the ``<li>`` tag.
        :param out: the :class:`StringIO` that collects the output.
        :param level: the embedding "level" of the list. Top-level lists have
                      _level_ ``0``, a list embedded into one _level_ ``1``,
                      etc.
        :param index: the position of the list item within the list. Needed
                      for ordered lists; ``0`` for unordered lists.
        """
        for child in li:
            # There should be only one
            if isinstance(child, NavigableString):
                # Need bullets / numbers
                if self.bullet:
                    bullet = f'{index}. ' if index else self.bullet
                else:
                    bullet = ''
                print(f'{self.indent * level}{bullet}{child}', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')
