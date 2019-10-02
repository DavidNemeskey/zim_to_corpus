#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Reader for the Project Gutenberg data in Kiwix's .zim file."""

import re

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from zim_to_corpus.html import headerp, listp

class ZimGutenbergParser:
    """
    Parses the HTML text of a book from Project Gutenberg to a cleaner and
    simpler HTML structure.

    .. warning::
    Note that this code can only parse the HTML in the Kiwix ZIM archives. The
    exact structure, class names, ids, etc. might be different from the HTML
    on the Project Gutenberg page. Also, due to the lack of a unified schema
    for PG books, the parser might drop valid text or include advertisements,
    etc.
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

    def parse_book(self) -> BeautifulSoup:
        """Parses a whole book."""
        self.new_bs.html.head.title.append(self.old_bs.find('title').get_text())

        # Let's start with the main content
        self.filter_tree()
        tmp_bs = self.pre_parse()
        return tmp_bs

    def pre_parse(self) -> BeautifulSoup:
        """
        Pre-parses the old html and adds headers, lists, paragraphs and poems
        to the new html.
        """
        old_body = self.old_bs.find('body')
        tmp_bs = BeautifulSoup(self.html_template)
        new_body = tmp_bs.html.body
        for tag in old_body.find_all(re.compile('^(?:p|ul|ol|h[1-5]|div)$')):
            if tag.name != 'div':
                new_tag = tmp_bs.new_tag(tag.name)
                if tag.name == 'p':
                    new_tag.append(' '.join(tag.get_text().split()))
                elif headerp.match(tag.name):
                    new_tag.append(tag.get_text())
                elif listp.match(tag.name):
                    for li in tag.children:
                        if isinstance(li, Tag) and li.name == 'li':
                            new_li = tmp_bs.new_tag('li')
                            new_li.append(' '.join(li.get_text().split()))
                            new_tag.append(new_li)
                new_body.append(new_tag)
            else:  # div
                if 'poem' not in tag.get('class', []):
                    continue
                print('Found poem')
                if tag.find('div', {'class': 'stanza'}):
                    print('Found stanza')
                    # One p per stanza
                    for stanza in tag.find_all('div', {'class': 'stanza'}):
                        new_p = tmp_bs.new_tag('p')
                        for line in stanza.find_all('span'):
                            new_p.append(line.get_text())
                        new_body.append(new_p)
                else:
                    print('No stanza found')
                    # Unstructured poem with lines as paragraphs
                    new_p = tmp_bs.new_tag('p')
                    for line in tag.find_all('p'):
                        new_p.append(line.get_text())
                    new_body.append(new_p)
        return tmp_bs

    def filter_tree(self):
        """Filters page numbers, tables and suchlike."""
        for pn in self.old_bs.find_all('span', {'class': 'pageno'}):
            pn.decompose()
        for pn in self.old_bs.find_all('span', {'class': 'pagenum'}):
            pn.decompose()
        for table in self.old_bs.find_all('table'):
            table.decompose()
