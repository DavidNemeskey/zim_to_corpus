#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that transform the HTML document content in one way or another.
"""

import re
from typing import Callable, Pattern, Set, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.tokenization import Tokenizer


def visit_tree(tree: Union[BeautifulSoup, Tag],
               string_callback: Callable[[int, str], None] = None,
               pre_tag_callback: Callable[[int, Tag], bool] = None,
               post_tag_callback: Callable[[int, Tag], None] = None):
    """
    A visitor that runs through the tree in a recursive fashion and calls a
    callback function for each node. Traversal is right-to-left. Callbacks
    receive the index of the child within _tree_ and the child itself.

    :param tree: the document tree.
    :param string_callback: the callback function invoked for
                            :class:`NavigableString`s.
    :param pre_tag_callback: the callback function invoked for :class:`Tag`s
                             _before_ descending to visit its children. If
                             the return value is ``False``, the children are
                             not visited at all. This is useful when e.g. the
                             tag is deleted.
    :param post_tag_callback: the callback function invoked for :class:`Tag`s
                              _after_ visiting its children.
    """
    # Have to do it in reverse order and with contents, so as to not invalidate
    # the iterator (children) or the index (i)
    for i in range(len(tree.contents) - 1, -1, -1):
        child = tree.contents[i]
        if isinstance(child, NavigableString):
            if string_callback:
                string_callback(i, child)
        else:
            print(f'tag {i} {child.name}', flush=True)
            if pre_tag_callback:
                if not pre_tag_callback(i, child):
                    print(f'continueuing', flush=True)
                    continue
            print('visiting', flush=True)
            visit_tree(child, string_callback,
                       pre_tag_callback, post_tag_callback)
            if post_tag_callback:
                post_tag_callback(i, child)


def unprettify(bs: BeautifulSoup):
    """
    Gets rid of all the whitespaces used solely for formatting. This includes
    deleting superfluous :class:`NavigableString`s in the HTML tree,
    as well as stripping whitespaces from around otherwise meaningful strings.
    """
    def strip_string(_, nav_string):
        stripped = nav_string.strip()
        if not stripped:
            nav_string.extract()
        elif stripped != nav_string:
            nav_string.replace_with(stripped)

    visit_tree(bs, strip_string)


def tokenize(bs: BeautifulSoup, tokenizer: Tokenizer):
    """Tokenizes all text in the page."""
    def do_tokenize(_, nav_string):
        nav_string.replace_with('\n'.join(' '.join(tokens) for tokens
                                          in tokenizer(nav_string)))

    visit_tree(bs, do_tokenize)


def add_ids(bs: BeautifulSoup):
    """Adds ids to all content tags."""
    valid_tags = re.compile('^section|ol|ul|li|p|h[0-9]+$')

    def add_id(tag_idx, tag):
        # We only give ids to tags under body.
        if valid_tags.match(tag.name):
            parent_id = tag.parent.attrs.get('id')
            tag_id = f'{tag.name[0]}{tag_idx + 1}'
            if parent_id:
                tag_id = f'{parent_id}-{tag_id}'
            tag.attrs['id'] = tag_id
        return True

    visit_tree(bs, pre_tag_callback=add_id)


def remove_tags(bs: BeautifulSoup, tags: Set[str] = None,
                pattern: Pattern = None):
    """
    Removes all tags (and associated subtrees) from the tree whose ``name``
    is in _tags_ or match _pattern_.
    """
    def pre_remove(_, tag):
        """Deletes tags with matching names."""
        if (tags and tag.name in tags) or (pattern and pattern.match(tag.name)):
            tag.decompose()
            return False
        else:
            return True

    def post_remove(_, tag):
        """Delete all tags that have become empty."""
        if not tag.contents:
            tag.decompose()

    visit_tree(bs, pre_tag_callback=pre_remove, post_tag_callback=post_remove)
