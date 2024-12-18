#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that convert from the canonical "simple HTML" format to various
other formats.
"""

from functools import partial
import json
from io import StringIO
import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.html import headerp, lip, listp
from zim_to_corpus.transformations import (
    add_ids, matches, remove_tags, replace_a_with_anchor
)
from zim_to_corpus.tokenization import Tokenizer

class Converter:
    """Base class for all converters."""
    def __init__(self, headers=True, lists=True):
        """
        Creates a new :class:`Converter`.

        Some formats, such as BERT, do not preserve headers nor lists. This
        class allows the user to decide, not only for BERT, but other formats
        as well.

        :param headers: whether headers should be included in the output.
        :param lists: whether lists should be included in the output.
        """
        self.headers = headers
        self.lists = lists

        pattern = []
        if not self.lists:
            pattern.append('ol|ul|li')
        if not self.headers:
            pattern.append('h[0-9]+')
        self.pattern = re.compile('|'.join(pattern)) if pattern else None

    def __call__(self, html: BeautifulSoup, title: str = '') -> str:
        """
        Converts _html_ to text in a specific format.

        :param html: the minimal HTML representation of a Wikipedia page.
        :param title: the document title. Only used if _to_json_ is ``True``.
        :param to_json: converts the document to a JSON dictionary, with the
                  text under the "text" key and the title under "id".
        :returns: the converted text, which might be empty, if the original
                  document was empty as well.
        """
        out = StringIO()
        self.convert_document(html, out)
        doc_text = out.getvalue()
        if doc_text.isspace():
            doc_text = ''
        return doc_text

    def header(self):
        """
        Text to print at the beginning of a file of converted documents. Noop
        for most converters.
        """
        pass

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """
        The topmost conversion function. This is also the place where lists
        and headers are removed, if requested.
        """
        if self.pattern:
            remove_tags(html, partial(matches, pattern=self.pattern))
        replace_a_with_anchor(html)
        body = html.find('body')
        if body:
            for section in (c for c in body.children if isinstance(c, Tag)):
                self.convert_section(section, out)

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
            if lip.fullmatch(child.name):
                self.convert_li(child, out, level,
                                position if lst.name == 'ol' else 0)
                position += 1
            else:
                raise ValueError(f'Unexpected tag {child.name} in list')


# TODO to corpus format
# TODO to markdown
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
    def __init__(self, tokenizer: Tokenizer,
                 bullet: str = None, indent: int = 0):
        """
        Creates a new :class:`WT2Converter`.

        :param tokenizer: used to tokenize the text.
        :param bullet: the character to use as bullets for lists. The default is
                       ``None``, which means no list bullets (or numbers)
                       will be used. This complies with the original WT-2 format.
        :param indent: the number of spaces to indent a list embedded in another.
        """
        super().__init__()
        self.tokenizer = tokenizer
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
                print(f'\n {mustache} {self.tokenizer.tokenize(child.get_text())} '
                      f'{mustache} \n', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            elif child.name == 'p':
                print(f' {self.tokenizer.tokenize(child.get_text())} ', file=out)
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
                print(f'{self.indent * level}{bullet} '
                      f'{self.tokenizer.tokenize(child)}', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')


class BERTConverter(Converter):
    def __init__(self, tokenizer: Tokenizer, headers=False, lists=False,
                 bullet: str = None, indent: int = 0):
        """
        Creates a new :class:`BERTConverter`.

        .. note::
        Neither headers nor lists are preserved in the original BERT format.
        This class includes an option to keep them for experimental purposes.

        .. note::
        The BERT format requires that each sentence be on its own line.
        The :mod:`zim_to_corpus.tokenization` module contains classes for
        sentence boundary detection.

        :param tokenizer: used for sentence boundary detection.
        :param bullet: the character to use as bullets for lists. The default is
                       ``None``, which means no list bullets (or numbers)
                       will be used. This complies with the original WT-2 format.
        :param indent: the number of spaces to indent a list embedded in another.
        """
        super().__init__(headers, lists)
        self.tokenizer = tokenizer

        self.bullet = f'{bullet} ' if bullet else ''
        self.indent = ' ' * indent

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """
        Removes headers and/or lists if so instructed in the constructor.

        .. warning::
        Removal is done in-place, so ``html`` will not include the tags affected
        after calling this method.
        """
        super().convert_document(html, out)
        print(file=out)

    def convert_section(self, section: Tag, out: StringIO):
        """
        Converts a section to text. The text is written to _out_.

        :param section: the section tag.
        :param out: the :class:`StringIO` that collects the output.
        """
        for child in section.children:
            if headerp.match(child.name):
                print(self.tokenizer.ssplit(child.get_text()), file=out)
            elif listp.match(child.name):
                self.convert_list(child, out)
            elif child.name == 'section':
                self.convert_section(child, out)
            elif child.name == 'p':
                print(self.tokenizer.ssplit(child.get_text()), file=out)
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
                print(f'{self.indent * level}{bullet}'
                      f'{self.tokenizer.ssplit(child)}', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')


class TsvConverter(Converter):
    WS = re.compile(r'\s')

    def __init__(self, tokenizer: Tokenizer, headers=True, lists=True,
                 bullet: str = None):
        """
        :param tokenizer: used for tokenization and sentence boundary detection.
        """
        super().__init__(headers, lists)
        self.tokenizer = tokenizer
        self.bullet = bullet

    def header(self):
        """Returns the name of the surface form column, according to CoNLL-U."""
        return 'form'

    def convert_document(self, html: BeautifulSoup, out: StringIO):
        """Prints the title of the document."""
        print(f'# newdoc id = {html.html.head.title.get_text()}', file=out)
        add_ids(html)
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
        li_text = StringIO()
        for child in li:
            # There should be only one
            if isinstance(child, NavigableString):
                # Need bullets / numbers
                if self.bullet:
                    bullet = f'{index}. ' if index else self.bullet
                else:
                    bullet = ''
                li_text.write(bullet + child)
                # self.print_sentences(li, bullet + child, out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                li_text.write(child.get_text())
                # raise ValueError(f'Unexpected tag {child.name} in list item')

        if li_value := li_text.getvalue():
            self.print_sentences(li, li_value, out)

    def print_sentences(self, id_tag: Tag, content: str, out: StringIO):
        print(f'# newpar id = {id_tag.attrs.get("id")}', file=out)
        for sentence in self.tokenizer(content):
            print(f'# text = {self.WS.sub(" ", sentence.text)}', file=out)
            for token in sentence.tokens:
                print(token, file=out)
            print(file=out)


class JsonlConverter(Converter):
    def __init__(self, tokenizer: Tokenizer, bullet: str = '-', indent: int = 4):
        """
        Creates a new :class:`JSONConverter`.

        :param tokenizer: not used.
        :param bullet: the character to use as bullets for lists. The default is
                       ``-``.
        :param indent: the number of spaces to indent a list embedded in
                       another. The default is 4.
        """
        super().__init__(True, True)

        self.bullet = f'{bullet} ' if bullet else ''
        self.indent = ' ' * indent

    def __call__(self, html: BeautifulSoup, title: str = '') -> str:
        doc_text = super().__call__(html, title).rstrip('\n')
        return json.dumps({'id': title, 'text': doc_text},
                          ensure_ascii=False) + '\n'

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
                print(child.get_text(), file=out)
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
                print(f'{self.indent * level}{bullet} {child}', file=out)
            elif listp.match(child.name):
                self.convert_list(child, out, level + 1)
            else:
                raise ValueError(f'Unexpected tag {child.name} in list item')
