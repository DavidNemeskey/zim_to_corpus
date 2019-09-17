#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stuff used for HTML parsing."""

import re

from bs4.element import Tag

# Pattern for recognizing headers
headerp = re.compile('[hH][0-9]+')
# Pattern for recognizing lists
listp = re.compile('[ou]l')


def get_title(section: Tag) -> str:
    """Returns the title of the section."""
    for child in section.children:
        if headerp.match(child.name):
            return child.get_text()
    else:
        raise ValueError('No header in section')
