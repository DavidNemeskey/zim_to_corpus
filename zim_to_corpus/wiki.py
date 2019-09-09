#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wikipedia-related functions."""

import gzip
from itertools import count
import re
import struct
from typing import Generator

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString


class ZimHtmlParser:
    """
    Parses the HTML text of a Wikipedia page. Due to the sorry state of the
    WP tooling, this is the only reliable way of extracting the text from
    a WP page.

    Of course, static HTML dumps are unsupported, so the only way of getting
    them is through the
    `Kiwix ZIM files <https://wiki.kiwix.org/wiki/Content_in_all_languages>`_.

    .. warning::
    Note that this code can only parse the HTML in the Kiwix ZIM archives. The
    exact structure, class names, ids, etc. are different from the HTML
    on wikipedia.org. Also, even some of the .zim files have differently
    structured HTMLs; however, the main Wikipedia dumps (_all_) should work.
    """
    html_template = """<html>
    <head>
        <title></title>
        <meta charset="UTF-8">
    </head>
    <body>
    </body>
</html>"""

    headerp = re.compile('[hH][0-9]+')
    listp = re.compile('[ou]l')

    def __init__(self, html_text):
        self.old_bs = BeautifulSoup(html_text)
        self.new_bs = BeautifulSoup(self.html_template)

    def simplify(self):
        self.new_bs.html.head.title.append(self.old_bs.find('title').get_text())

        # Let's start with the main content
        old_body = self.old_bs.find('div', id='mw-content-text')
        # Let's get rid of the references now
        for sup in old_body.find_all('sup', {'class': 'mw-ref'}):
            sup.decompose()
        for child in old_body.children:
            if child.name == 'section':
                self.parse_section(child, self.new_bs.html.body)

        # Add the first (title) header, which is usually outside of mw-content-text
        title = self.old_bs.find(id='titleHeading')
        if title and not self.new_bs.find('h1'):
            first_section = self.new_bs.find('section')
            if first_section:
                self.add_tag(title.name, title.get_text(), first_section, 0)

        return self.new_bs

    def parse_section(self, old_section, new_parent):
        new_section = self.new_bs.new_tag('section')
        for child in self.filter_tags(old_section):
            if isinstance(child, NavigableString):
                # TODO out-of-order NavigableString
                pass
            if child.name == 'section':
                self.parse_section(child, new_section)
            elif child.name == 'p':
                text = ' '.join(child.get_text().split())
                if text:
                    self.add_tag('p', text, new_section)
            elif self.headerp.match(child.name):
                self.add_tag(child.name, child.get_text(), new_section)
            elif self.listp.match(child.name):
                self.parse_list(child, new_section)

        # Only append non-empty sections
        if list(new_section.children):
            new_parent.append(new_section)

    def parse_list(self, old_list, new_parent):
        new_list = self.new_bs.new_tag(old_list.name)
        for child in self.filter_tags(old_list):
            if isinstance(child, NavigableString):
                raise ValueError(f'Unexpected navigablestring in {old_list.name}')
            elif child.name != 'li':
                raise ValueError(f'Unexpected tag {child.name} in {old_list.name}')
            else:
                self.parse_li(child, new_list)

        # Only append non-empty lists
        if list(new_list.children):
            new_parent.append(new_list)

    def parse_li(self, old_li, new_list):
        new_li = self.new_bs.new_tag('li')

        content = []
        for child in self.filter_tags(old_li, False):
            if isinstance(child, NavigableString):
                content.append(child)
            elif self.listp.match(child.name):
                self.parse_list(child, new_li)
            else:
                content.append(child.get_text())

        content = ' '.join(' '.join(content).split())
        if content:
            new_li.insert(0, content)
        if list(new_li.children):
            new_list.append(new_li)

    def add_tag(self, name, content, parent, position=None, **kwattrs):
        tag = self.new_bs.new_tag(name, **kwattrs)
        tag.append(content)
        if position is not None:
            parent.insert(position, tag)
        else:
            parent.append(tag)
        return tag

    @staticmethod
    def filter_tags(tag, empty_strings_too=True):
        """Enumerates the non-comment, non-newline children of _tag_."""
        for child in tag.children:
            if isinstance(child, Comment):
                continue
            elif isinstance(child, NavigableString) and empty_strings_too:
                if child.strip():
                    yield child
            else:
                yield child

    @staticmethod
    def parse(html_text):
        return ZimHtmlParser(html_text).simplify()


def enumerate_static_dump(static_dump_file: str) -> Generator[str, None, None]:
    """
    Reads the specified static Wikipedia HTML dump file (the output of
    :command:`zim_to_dir`) and enumerates all pages therein.
    """
    with gzip.open(static_dump_file, 'rb') as inf:
        for doc_no in count(1):
            size_raw = inf.read(4)
            if len(size_raw) != 4:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            elif not size_raw:
                break
            size = struct.unpack('!i', size_raw)[0]
            html_raw = inf.read(size)
            if len(html_raw) != size:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            html = html_raw.decode('utf-8')
            yield html
