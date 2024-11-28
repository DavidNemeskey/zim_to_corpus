#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stuff used for HTML parsing."""

from itertools import groupby
import re
from typing import Generator, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

# Pattern for recognizing headers
headerp = re.compile('[hH][0-9]+')
# Patterns for recognizing lists
listp = re.compile('[oud]l')
lip = re.compile('li|d[dt]')

# Template for the simplified html used for normalized documents
html_template = """<html>
    <head>
        <title></title>
        <meta charset="UTF-8">
    </head>
    <body></body>
</html>"""


def get_section_title_tag(section: Tag, exception: bool = True) -> Tag:
    """
    Returns the title (first header) tag of the section.

    :param section: the section tag.
    :param exception: can be set to ``False`` to make the function return
                      ``None`` instead of throwing an exception if the
                      section has no header.
    :return: the header **tag**.
    """
    for child in section.children:
        if headerp.match(child.name):
            return child
    else:
        if exception:
            raise ValueError('No header in section')
        else:
            return None


def get_section_title(section: Tag) -> str:
    """Returns the title (first header) of the section."""
    return get_section_title_tag(section).get_text().strip()


def get_html_title(bs: BeautifulSoup) -> str:
    """Returns the title of an HTML page."""
    title = bs.find('title')
    return title.get_text().strip() if title else None


def sections_backwards(tree: Union[BeautifulSoup, Tag]) -> Generator[Tag, None, None]:
    """Enumerates the sections in a document or HTML tree in reverse order."""
    if isinstance(tree, BeautifulSoup):
        yield from sections_backwards(tree.body)
    for child in tree.contents[::-1]:
        if isinstance(child, Tag) and child.name == 'section':
            yield from sections_backwards(child)
    else:
        if tree.name == 'section':
            yield tree


def _merge_strings(tag: Union[BeautifulSoup, Tag], bs: BeautifulSoup):
    """Inner implementation of :func:`merge_strings`."""
    to_replace = []
    index = 0
    for typ, it in groupby(tag.contents, key=type):
        nodes = list(it)
        if issubclass(typ, NavigableString):
            if len(nodes) > 1:
                to_replace.append((index, len(nodes), ''.join(nodes)))
        else:
            for node in nodes:
                _merge_strings(node, bs)
        index += len(nodes)
    for index, length, string in to_replace[::-1]:
        for _ in range(length):
            tag.contents[index].extract()
        tag.insert(index, bs.new_string(string))


def merge_strings(tag: Union[BeautifulSoup, Tag], bs: BeautifulSoup = None):
    """
    Merges consecutive :class:`NavigableString`s in _tag_. Recursive.

    :param tag: the root of the tree in which to merge strings.
    :param bs: the :class:`BeautifulSoup` instance, which is needed to
               create strings.  Can be ``None``, but in that case, _tag_
               must be a :class:`BeautifulSoup` instance.
    """
    if bs is None:
        if not isinstance(tag, BeautifulSoup):
            raise ValueError('Either bs must be specified or tag must be '
                             f'a BeautifulSoup instance, not {type(tag)}.')
        bs = tag
    return _merge_strings(tag, bs)


def count_characters_in_p_tags(bs: BeautifulSoup):
    return sum(len(tag.get_text(strip=True)) for tag in bs.find_all('p'))
