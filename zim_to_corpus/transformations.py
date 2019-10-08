#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions that transform the HTML document content in one way or another.
"""

from functools import wraps
import re
from typing import Callable, Pattern, Set, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from zim_to_corpus.html import headerp, get_title


class StopVisitor(Exception):
    pass


def stoppable(func: Callable):
    """
    A decorator that makes _func_ safely stoppable with the :class:`StopVisitor`
    exception ("safely" as in wrapped in a ``try``-``except`` block).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StopVisitor:
            pass

    return wrapper


@stoppable
def visit_tree(tree: Union[BeautifulSoup, Tag],
               string_callback: Callable[[int, str], None] = None,
               pre_tag_callback: Callable[[int, Tag], bool] = None,
               post_tag_callback: Callable[[int, Tag], None] = None):
    """
    A visitor that runs through the tree in a recursive fashion and calls a
    callback function for each node. Traversal is right-to-left. Callbacks
    receive the index of the child within _tree_ and the child itself.

    Callbacks can raise a :class:`StopVisitor` exception to stop the visitor.

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
            if pre_tag_callback:
                if not pre_tag_callback(i, child):
                    continue
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


def is_empty(tag: Tag) -> bool:
    """
    Tells whether _tag_ is "empty", i.e. it has no children, or, if it is a
    section, it only has header children.
    """
    if not tag.contents:
        return True
    elif tag.name == 'section' and all(headerp.match(t.name)
                                       for t in tag.contents):
        return True
    return False


def remove_tags(bs: BeautifulSoup, predicate: Callable[[int, Tag], bool]):
    """
    Removes all tags (and associated subtrees) from the tree for which
    ``predicate`` is ``True``. All tags that become empty as a result will
    be removed as well.

    :param bs: the document.
    :param predicate: a function that takes the index of the tag (within its
                      parent's children list) and the tag itself and returns
                      ``True`` if it has to be deleted and ``False`` otherwise.
    """
    def pre_remove(tag_idx: int, tag: Tag) -> bool:
        """Deletes tags with matching names."""
        if predicate(tag_idx, tag):
            tag.decompose()
            return False
        else:
            return True

    def post_remove(_, tag: Tag):
        """
        Delete all tags that have become empty, as well as sections with
        nothing but the header.
        """
        if is_empty(tag):
            tag.decompose()

    visit_tree(bs, pre_tag_callback=pre_remove, post_tag_callback=post_remove)


def in_set(tag_idx: int, tag: Tag, tags: Set[str]) -> bool:
    """
    A predicate for use in :func:`remove_tags`. Returns ``True`` if _tags_
    contains _tag_'s ``name``.

    .. note::
    While this function can be imitated with
    ``lambda _, tag: tag.name in {...}``, that would create the set on each
    invocation, so using ``in_set`` with :func:`functools.partial` is probably
    better in terms of performance.
    """
    return tag in tags


def matches(tag_idx: int, tag: Tag, pattern: Pattern) -> bool:
    """
    A predicate for use in :func:`remove_tags`. Returns ``True`` if _tag_'s
    ``name`` is matched by ``pattern``.

    .. note::
    While this function can be imitated with
    ``lambda _, tag: tag.name in {...}``, that would create the set on each
    invocation, so using ``in_set`` with :func:`functools.partial` is probably
    better in terms of performance.
    """
    return pattern.match(tag.name)


def remove_empty_tags(bs: BeautifulSoup):
    """Removes all empty tags from the tree."""
    def post_remove(_, tag):
        if is_empty(tag):
            tag.decompose()

    visit_tree(bs, post_tag_callback=post_remove)


def remove_sections(bs: BeautifulSoup, sections: Set[str]):
    """
    Removes consecutive sections from the end of the document whose names are
    contained in _sections_. The functions stops when the first section not in
    the set is met.
    """
    def post_remove(_, tag):
        if tag.name == 'section':
            try:
                title = get_title(tag)
            except ValueError:
                title = None
            if title in sections:
                tag.decompose()
            elif is_empty(tag):
                tag.decompose()
            else:
                raise StopVisitor(f'First section not in set: {title}')

    visit_tree(bs, post_tag_callback=post_remove)
