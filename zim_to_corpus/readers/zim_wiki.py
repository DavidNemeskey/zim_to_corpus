#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wikipedia-related functions."""

import logging
from typing import Generator, Union

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from zim_to_corpus.html import headerp, listp


class ZimHtmlParser:
    """
    Parses the HTML text of a Wikipedia page to a simpler and cleaner HTML
    structure. Due to the sorry state of the WP tooling, this is the only
    reliable way of extracting the text from a WP page.

    Of course, static HTML dumps are unsupported, so the only way of getting
    them is through the
    `Kiwix ZIM files <https://wiki.kiwix.org/wiki/Content_in_all_languages>`_.

    .. warning::
    Note that this code can only parse the HTML in the Kiwix ZIM archives. The
    exact structure, class names, ids, etc. are different from the HTML
    on wikipedia.org. Also, even some of the .zim files have differently
    structured HTMLs; however, the main Wikipedia dumps (_all_) should work.
    """
    # Template for the output (simplified) html
    html_template = """<html>
    <head>
        <title></title>
        <meta charset="UTF-8">
    </head>
    <body></body>
</html>"""

    def __init__(self, html_text: str):
        self.old_bs = BeautifulSoup(html_text)
        self.new_bs = BeautifulSoup(self.html_template)
        self.title = self.old_bs.find('title').get_text()

    def simplify(self) -> BeautifulSoup:
        """Does the conversion / simplification."""
        self.new_bs.html.head.title.append(self.old_bs.find('title').get_text())

        # Let's start with the main content
        old_body = self.old_bs.find('div', id='mw-content-text')
        self.filter_tree(old_body)
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

    def filter_tree(self, tree: Tag):
        """Filters references from the text."""
        for sup in tree.find_all('sup', {'class': 'mw-ref'}):
            sup.decompose()
        # And linkback texts
        for linkback in tree.find_all('span', {'class': 'mw-linkback-text'}):
            linkback.decompose()
        # And note divs (For the XXX, see YYY). These only exist in the
        # English Wikipedia, not in the Hungarian one
        for div in tree.find_all('div', {'role': 'note'}):
            div.decompose()

    def parse_section(self, old_section: Tag, new_parent: Tag):
        """
        Parses a section. Only adds the simplified section to the new DOM if
        it is not empty.

        :param old_section: the section tag in the DOM of the original page.
        :param new_parent: the to-be-parent of section tag in simplified DOM.
                           Mostly `<body>` or another `<section>`.
        """
        new_section = self.new_bs.new_tag('section')
        for child in self.filter_tags(old_section):
            if isinstance(child, NavigableString):
                logging.warning(f'NavigableString >{child}< in '
                                f'{old_section.name} in {self.title}.')
                # raise ValueError(f'NavigableString >{child}< in {old_section.name}')
            elif child.name == 'section':
                self.parse_section(child, new_section)
            elif child.name == 'p':
                text = ' '.join(child.get_text().split())
                if text:
                    self.add_tag('p', text, new_section)
            elif child.name == 'div':
                self.parse_div(child, new_section)
            elif headerp.match(child.name):
                self.add_tag(child.name, child.get_text(), new_section)
            elif listp.match(child.name):
                self.parse_list(child, new_section)

        # Only append non-empty sections (having a single header still counts
        # as empty)
        if [c for c in new_section.children if not headerp.match(c.name)]:
            new_parent.append(new_section)

    def parse_div(self, old_div: Tag, new_section: Tag):
        """
        Sometimes there are divs between the sections and the lower-level tags,
        such as ``p`` or lists. This method is basically the same as
        :meth:`parse_section`, only it doesn't allow ``section``s inside of
        the ``div``.
        """
        for child in self.filter_tags(old_div):
            if isinstance(child, NavigableString):
                logging.warning(f'NavigableString >{child}< in '
                                f'div in {self.title}.')
                # raise ValueError(f'NavigableString >{child}< in {old_section.name}')
            elif child.name == 'p':
                text = ' '.join(child.get_text().split())
                if text:
                    self.add_tag('p', text, new_section)
            elif child.name == 'div':
                self.parse_div(child, new_section)
            elif child.name == 'section':
                logging.warning(f'section in div in {self.title}.')
            elif headerp.match(child.name):
                self.add_tag(child.name, child.get_text(), new_section)
            elif listp.match(child.name):
                self.parse_list(child, new_section)

    def parse_list(self, old_list: Tag, new_parent: Tag):
        """
        Parses a(n ordered or unordered) list. Only adds the simplified list to
        the new DOM if it is not empty.

        :param old_list: the `ol` or `ul` tag in the DOM of the original page.
        :param new_parent: the to-be-parent of list tag in simplified DOM.
        """
        new_list = self.new_bs.new_tag(old_list.name)
        for child in self.filter_tags(old_list):
            if isinstance(child, NavigableString):
                logging.warning(f'Unexpected navigablestring >{child}< in '
                                f'{old_list.name} in {self.title}')
                # raise ValueError(f'Unexpected navigablestring >{child}< in {old_list.name}')
            elif child.name != 'li':
                if child.name in ('span', 'div'):
                    text = child.get_text()
                    if text.strip():
                        # Just warning, so that we don't break parsing
                        logging.warning(f'Unexpected tag {child.name} '
                                        f'>{text}< in {old_list.name}')
            else:
                self.parse_li(child, new_list)

        # Only append non-empty lists
        if list(new_list.children):
            new_parent.append(new_list)

    def parse_li(self, old_li, new_list):
        """
        Parses a list item. Only adds the simplified item to
        the new DOM if it is not empty.

        :param old_li: the `li` tag in the DOM of the original page.
        :param new_list: the list tag in simplified DOM.
        """
        new_li = self.new_bs.new_tag('li')

        content = []
        for child in self.filter_tags(old_li, False):
            if isinstance(child, NavigableString):
                content.append(child)
            elif listp.match(child.name):
                self.parse_list(child, new_li)
            else:
                content.append(child.get_text())

        content = ' '.join(' '.join(content).split())
        if content:
            new_li.insert(0, content)
        if list(new_li.children):
            new_list.append(new_li)

    def add_tag(self, name: str, content: str, parent: Tag,
                position: int = None, **kwattrs: str):
        """
        Adds a new tag under a parent tag with textual content.

        :param name: the name of the new tag (e.g. `p`)
        :param content: its content.
        :param parent: the tag under which the new tag is put.
        :param position: if `None` (the default), the new tag is appended to
                         the children of _parent_; otherwise, it is inserted at
                         the specified position.
        :returns: the newly created tag.
        """
        tag = self.new_bs.new_tag(name, **kwattrs)
        tag.append(content)
        if position is not None:
            parent.insert(position, tag)
        else:
            parent.append(tag)
        return tag

    @staticmethod
    def filter_tags(tag: Tag, empty_strings_too=True) -> Generator[
            Union[Tag, NavigableString], None, None
    ]:
        """
        Enumerates the non-comment, non-empty children of _tag_.

        :param tag: the tag whose children are filtered.
        :param empty_strings_too: if `True` (the default), all empty
                                  `<span>`, `<div>` or :class:`NavigableString`
                                  children are filtered as well.
        """
        for child in tag.children:
            if isinstance(child, Comment):
                continue
            elif isinstance(child, NavigableString) and empty_strings_too:
                if child.strip():
                    yield child
            else:
                yield child


def parse(html_text: str) -> BeautifulSoup:
    """Convenience method for ``ZimHtmlParser(html_text).simplify()``."""
    return ZimHtmlParser(html_text).simplify()
