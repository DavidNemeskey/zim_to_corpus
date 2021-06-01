#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wikipedia-related functions."""

import copy
import logging
from typing import Generator, Iterable, Mapping, Union

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from zim_to_corpus.html import (
    headerp, lip, listp, html_template, merge_strings
)


TagOrSoup = Union[BeautifulSoup, Tag]


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
    def __init__(self, html_bytes: bytes,
                 retain_tags: Mapping[str, bool] = None,
                 tag_replacements: Mapping[str, str] = None):
        """
        :param html_bytes: the raw HTML.
        :param retain: the names of tags to keep in the text.
        :param replacements: a tag name ``->`` replacement mapping for
                             tags to replace with a placeholder string.
        """
        self.old_bs = BeautifulSoup(html_bytes)
        self.new_bs = BeautifulSoup(html_template)
        self.title = self.old_bs.find('title').get_text()
        self.retain = {'p': False, 'h1': False, 'h2': False, 'h3': False,
                       'h4': False, 'h5': False, 'h6': False}
        self.retain.update(dict(retain_tags or {}))
        self.replacements = dict(tag_replacements or {})

    def simplify(self) -> BeautifulSoup:
        """Does the conversion / simplification."""
        self.new_bs.html.head.title.append(self.title)

        # Let's start with the main content
        old_body = self.old_bs.find('div', id='mw-content-text')
        self.filter_tree(old_body)
        # Parse section is recursive, and we call it on body so that it is
        # put into
        self.parse_section(old_body, self.new_bs.html.body)

        # Add the first (title) header, which is usually outside of mw-content-text
        title = self.old_bs.find(id='title_0')
        # Only add the title if we don't already have a h1
        if title and not self.new_bs.find('h1'):
            first_section = self.new_bs.find('section')
            if first_section:
                self.add_tag('h1', title.get_text(), first_section, 0)

        # Getting rid of the consecutive NavigableStrings, which look ugly
        # prettify()'d.
        merge_strings(self.new_bs)
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
        # And style elements, which are not limited to <HEAD>... however,
        # these seem not to be present in the output of the latest version /
        # the pinned lxml version
        for sup in tree.find_all('style'):
            sup.decompose()

    def parse_math(self, node: Tag, new_parent: Tag):
        """Parses the <math> tag into a sinle line."""
        new_parent.append(' '.join(node.get_text().split()))

    def parse_generic(self, node: Tag, new_parent: Tag):
        """
        Parses a generic _node_ in the old DOM and adds (a simplified form of)
        its contents to _new_parent_ in the new one. The lists of tags to
        retain and replace, passed to :meth:`__init__`, are honored; of all
        the other tags, only the text is kept.
        """
        if isinstance(node, NavigableString):
            new_parent.append(copy.copy(node))
        elif (rep := self.replacements.get(node.name)):
            new_parent.append(rep)
        elif node.name == 'math':
            self.parse_math(node, new_parent)
        elif node.name in self.retain:
            attrs = node.attrs if self.retain[node.name] else {}
            # new_tag = self.add_tag(node.name, '', new_parent, **attrs)
            new_tag = self.new_bs.new_tag(node.name, **attrs)
            for child in self.filter_tags(node, False):
                self.parse_generic(child, new_tag)
            if new_tag.contents:
                new_parent.append(new_tag)
        else:
            for child in self.filter_tags(node, False):
                self.parse_generic(child, new_parent)

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
            elif child.name == 'details':
                self.parse_section(child, new_section)
            elif child.name == 'p':
                self.parse_generic(child, new_section)
            elif child.name == 'div':
                self.parse_div(child, new_section)
            elif child.name == 'summary' and 'section-heading' in child.get('class'):
                for gc in child.children:
                    if headerp.match(gc.name):
                        self.parse_generic(gc, new_section)
            elif listp.match(child.name):
                self.parse_list(child, new_section)

        # Only append non-empty sections (having a single header still counts
        # as empty)
        if [c for c in new_section.children if not (c.name and headerp.match(c.name))]:
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
                self.parse_generic(child, new_section)
                # text = ' '.join(self.get_text(child).split())
                # if text:
                #     self.add_tag('p', text, new_section)
            elif child.name == 'div':
                self.parse_div(child, new_section)
            elif child.name == 'details':
                logging.warning(f'section in div in {self.title}.')
            elif headerp.match(child.name):
                # self.add_tag(child.name, self.get_text(child), new_section)
                self.parse_generic(child, new_section)
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
            elif lip.match(child.name):
                self.parse_li(child, new_list)
            elif child.name in ('span', 'div'):
                # text = self.get_text(child)
                text = child.get_text()
                if text.strip():
                    # Just warning, so that we don't break parsing
                    logging.warning(f'Unexpected tag {child.name} '
                                    f'>{text}< in {old_list.name}')

        # Only append non-empty lists
        if new_list.contents:
            new_parent.append(new_list)

    def parse_li(self, old_li, new_list):
        """
        Parses a list item. Only adds the simplified item to
        the new DOM if it is not empty.

        :param old_li: the `li` tag in the DOM of the original page.
        :param new_list: the list tag in simplified DOM.
        """
        new_li = self.new_bs.new_tag(old_li.name)

        content = []
        for child in self.filter_tags(old_li, False):
            if isinstance(child, NavigableString):
                new_li.append(copy.copy(child))
            elif listp.match(child.name):
                self.parse_list(child, new_li)
            else:
                self.parse_generic(child, new_li)
                # content.append(self.get_text(child))

        if new_li.contents:
            new_list.append(new_li)

    def add_tag(self, name: str, content: str, parent: Tag,
                position: int = None, **kwattrs: str) -> Tag:
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


def parse(html_bytes: bytes, *args, **kwargs) -> BeautifulSoup:
    """Convenience method for ``ZimHtmlParser(html_text).simplify()``."""
    return ZimHtmlParser(html_bytes, *args, **kwargs).simplify()
