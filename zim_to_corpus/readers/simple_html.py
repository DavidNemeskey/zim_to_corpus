#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Reader for the intermediate "simple HTML" format."""

from bs4 import BeautifulSoup
from bs4.element import NavigableString


def parse(html_text: str) -> BeautifulSoup:
    """
    Parses _html_text_, which represents a page in the "simple HMTL" format,
    and returns the corresponding :class:`BeautifulSoup` instance. Empty
    :class:`NavigableString`s are dropped.
    """
    bs = BeautifulSoup(html_text)
    for tag in bs.find_all():
        if isinstance(tag, NavigableString):
            if not tag.strip():
                tag.decompose()
    return bs
