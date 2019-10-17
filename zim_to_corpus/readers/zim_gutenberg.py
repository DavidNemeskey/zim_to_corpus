#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reader for the Project Gutenberg data in Kiwix's .zim file.

Parses the HTML text of a book from Project Gutenberg to a cleaner and
simpler HTML structure.

.. warning::
Note that this code can only parse the HTML in the Kiwix ZIM archives. The
exact structure, class names, ids, etc. might be different from the HTML
on the Project Gutenberg page. Also, due to the lack of a unified schema
for PG books, the parser might drop valid text or include advertisements,
etc.
"""

import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from zim_to_corpus.html import headerp, listp, html_template
from zim_to_corpus.transformations import remove_empty_tags


def filter_tree(tree: BeautifulSoup):
    """Filters page numbers, tables and suchlike."""
    for pn in tree.find_all('span', {'class': 'pageno'}):
        pn.decompose()
    for pn in tree.find_all('span', {'class': 'pagenum'}):
        pn.decompose()
    for table in tree.find_all('table'):
        table.decompose()

def pre_parse(old_bs: BeautifulSoup, keep_poems: bool = False) -> BeautifulSoup:
    """
    Pre-parses the old html and adds headers, lists, paragraphs and poems
    to the new html.
    """
    def add_text(old_tag: Tag, new_tag: Tag, new_parent: Tag):
        text = ' '.join(old_tag.get_text().split())
        if text:
            new_tag.append(text)
            new_parent.append(new_tag)

    old_body = old_bs.find('body')
    tmp_bs = BeautifulSoup(html_template)
    new_body = tmp_bs.html.body
    for tag in old_body.find_all(re.compile('^(?:p|ul|ol|h[1-5]|div)$')):
        if tag.name != 'div':
            new_tag = tmp_bs.new_tag(tag.name)
            if tag.name == 'p':
                add_text(tag, new_tag, new_body)
            elif headerp.match(tag.name):
                add_text(tag, new_tag, new_body)
            elif listp.match(tag.name):
                for li in tag.children:
                    if isinstance(li, Tag) and li.name == 'li':
                        new_li = tmp_bs.new_tag('li')
                        add_text(li, new_li, new_tag)
                if new_tag.contents:
                    new_body.append(new_tag)
        else:  # div
            if 'poem' in tag.get('class', []) and keep_poems:
                if tag.find('div', {'class': 'stanza'}):
                    # One p per stanza
                    for stanza in tag.find_all('div', {'class': 'stanza'}):
                        new_p = tmp_bs.new_tag('p')
                        for line in stanza.find_all('span'):
                            new_p.append(line.get_text().strip() + '\n')
                        if new_p.contents:
                            new_body.append(new_p)
                else:
                    # Unstructured poem with lines as paragraphs
                    new_p = tmp_bs.new_tag('p')
                    for line in tag.find_all('p'):
                        new_p.append(line.get_text().strip() + '\n')
                    if new_p.contents:
                        new_body.append(new_p)
    return tmp_bs


def add_sections(old_bs: BeautifulSoup):
    new_bs = BeautifulSoup(html_template)
    old_body = old_bs.html.body
    new_body = new_bs.html.body
    section = new_bs.new_tag('section')
    last_added = None
    # Note: the first 5 lines are a replacement of the proper for loop
    # commented out below. The reason for this is that when a tag is added
    # to a section, somehow the children iterator is messed up and as a
    # result, only every second tag is added to the section. So clumsy
    # while loop it is

    # for tag in old_body.children:
    while True:
        try:
            tag = next(old_body.children)
        except StopIteration:
            break
        if not isinstance(tag, Tag):
            print(f'WARNING, not tag: {tag}')
        if headerp.match(tag.name):
            if last_added and not headerp.match(last_added):
                if section.contents:
                    new_body.append(section)
                section = new_bs.new_tag('section')
        section.append(tag)
        last_added = tag.name
    if section.contents:
        new_body.append(section)

    remove_empty_tags(new_bs.html.body)
    return new_bs


def parse(html_bytes: bytes, keep_poems: bool = False, max_loss: float = 0.9,
          *args, **kwargs) -> BeautifulSoup:
    """Parses a whole book."""
    # Let's start with the main content
    old_bs = BeautifulSoup(html_bytes)
    old_len = len(' '.join(old_bs.get_text().split()))
    filter_tree(old_bs)
    tmp_bs = pre_parse(old_bs, keep_poems)
    new_bs = add_sections(tmp_bs)
    new_len = len(' '.join(new_bs.get_text().split()))
    title = old_bs.find('title')
    if title:
        new_bs.html.head.title.append(title.get_text())
    # Get rid of the document if it lost too much of its content (i.e. it was
    # a poem)
    if new_len / old_len < (1 - max_loss):
        new_bs.html.body.decompose()
    return new_bs
