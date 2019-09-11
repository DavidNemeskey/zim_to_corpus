#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that convert from the canonical "simple HTML" format to various
other formats.
"""

from io import StringIO
import re
from typing import Dict

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.html import headerp, listp
from zim_to_corpus.transformations import remove_tags

class Converter:
    """Base class for all converters."""
    def __call__(self, html: BeautifulSoup) -> str:
        """
        Converts _html_ to text in a specific format.

        :param html: the minimal HTML representation of a Wikipedia page.
        :returns: the converted text.
        """
        out = StringIO()
        self.convert_document(html, out)
        return out.getvalue()

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """The topmost conversion function."""
        for section in (c for c in html.find('body').children if isinstance(c, Tag)):
            self.convert_section(section, out)

    @classmethod
    def default_tokenization(cls) -> Dict[str, bool]:
        """
        Returns the default tokenization presets for the converter. These are
        the parameters accepted by all
        :class:`zim_to_corpus.tokenizerion.Tokenizer`s. The default of the
        default is no tokenization or sentence splitting.
        """
        return {'split_sentences': False, 'tokenize': False}

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


# TODO to corpus format
# TODO to markdown
# TODO to CoNNL-U
# TODO section filtering
class WT2Converter(Converter):
    """
    Converts from the "simple HTML" to WT-2 format.

    .. note::
    The original WT-2 format contains tokenized text. To adhere to that,
    the text in the HTML should be tokenized, but (preferably) not splitted at
    sentence boundaries. The :mod:`zim_to_corpus.tokenization` module contains
    the necessary machinery.
    """
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

    @classmethod
    def default_tokenization(cls) -> Dict[str, bool]:
        """
        Returns the default tokenization presets for the converter. These are
        the parameters accepted by all
        :class:`zim_to_corpus.tokenizerion.Tokenizer`s. The default of the
        default is no tokenization or sentence splitting.
        """
        return {'split_sentences': False, 'tokenize': True}

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

        .. note::
        The BERT format requires that each sentence be on its own line.
        The :mod:`zim_to_corpus.tokenization` module contains classes for
        sentence boundary detection, which has to be done prior to calling
        this converter.

        :param headers: whether headers should be included in the output.
        :param lists: whether lists should be included in the output.
        :param bullet: the character to use as bullets for lists. The default is
                       ``None``, which means no list bullets (or numbers)
                       will be used. This complies with the original WT-2 format.
        :param indent: the number of spaces to indent a list embedded in another.
        """
        self.headers = headers
        self.lists = lists

        pattern = []
        if not self.lists:
            pattern.append('ol|ul|li')
        if not self.headers:
            pattern.append('h[0-9]+')
        self.pattern = re.compile('|'.join(pattern)) if pattern else None

        self.bullet = f'{bullet} ' if bullet else ''
        self.indent = ' ' * indent

    @classmethod
    def default_tokenization(cls) -> Dict[str, bool]:
        """
        Returns the default tokenization presets for the converter. These are
        the parameters accepted by all
        :class:`zim_to_corpus.tokenizerion.Tokenizer`s. The default of the
        default is no tokenization or sentence splitting.
        """
        return {'split_sentences': True, 'tokenize': False}

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """
        Removes headers and/or lists if so instructed in the constructor.

        .. warning::
        Removal is done in-place, so ``html`` will not include the tags affected
        after calling this method.
        """
        if self.pattern:
            remove_tags(html, pattern=self.pattern)
        return super().convert_document(html, out)

    def convert_section(self, section: Tag, out: StringIO):
        """
        Converts a section to text. The text is written to _out_.

        :param section: the section tag.
        :param out: the :class:`StringIO` that collects the output.
        """
        for child in section.children:
            if headerp.match(child.name):
                print(child.get_text(), file=out)
            elif listp.match(child.name):
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


class TsvConverter(Converter):
    def __init__(self, headers=False, lists=False, bullet: str = None):
        self.bullet = bullet

    @classmethod
    def default_tokenization(cls) -> Dict[str, bool]:
        """
        Returns the default tokenization presets for the converter. These are
        the parameters accepted by all
        :class:`zim_to_corpus.tokenizerion.Tokenizer`s. The default of the
        default is no tokenization or sentence splitting.
        """
        return {'split_sentences': True, 'tokenize': True}

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """Prints the title of the document."""
        print(f'# newdoc id = {html.html.head.title.get_text()}', file=out)
        return super().convert_document(html, out)

    def convert_section(self, section: Tag, out: StringIO):
        for child in section.children:
            if headerp.match(child.name) or child.name == 'p':
                self.print_sentences(child, child.get_text(), out)
            elif listp.match(child.name):
                self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            else:
                raise ValueError(f'Unexpected tag {child.name} in section')

    def convert_li(self, li: Tag, out: StringIO, level: int, index: int):
        """
        Converts a list item to text. The text is written to _out_.

        :param lst: the ``<li>`` tag.
        :param out: the :class:`StringIO` that collects the output.
        :param level: unused.
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
                self.print_sentences(li, bullet + child, out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')

    def print_sentences(self, id_tag: Tag, content: str, out: StringIO):
        print(f'# newpar id = {id_tag.attrs.get("id")}', file=out)
        for sentence in content.split('\n'):
            # TODO: this is more complicated than it looks...
            print(f'# text = {sentence}', file=out)
            for token in sentence.split():
                print(token, file=out)
            print(file=out)
