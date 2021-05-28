#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stuff used for HTML parsing."""

import re
from typing import Generator, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

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


def get_section_title_tag(section: Tag) -> Tag:
    """Returns the title (first header) tag of the section."""
    for child in section.children:
        if headerp.match(child.name):
            return child
    else:
        raise ValueError('No header in section')


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
