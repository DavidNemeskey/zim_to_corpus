#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wikipedia-related functions."""

import gzip
from itertools import count
import struct
from typing import Generator

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString


class Unit(list):
    """A unit of Wikipedia content. A subclass of `list`."""
    def __init__(self, *children):
        super().__init__(*children)

    def add(self, unit: 'Unit') -> 'Unit':
        """
        Adds a unit under this one.

        :returns: the new unit.
        """
        self.append(unit)
        return unit

    def __str__(self):
        params = self.params()
        params_str = f'({params})' if params else ''
        return f'{self.__class__.__name__}{params_str}:[' + ', '.join(
            str(c) for c in self) + ']\n'

    def params(self):
        """
        Returns the unit-specific parameters that should be displayed by
        :meth:`__str__`.
        """
        return None

    def to_html(self, outf, indent=0):
        for unit in self:
            if isinstance(unit, Unit):
                unit.to_html(outf, indent + 4)


class WikiPage(Unit):
    """:class:`Unit` representing a whole Wikipedia page (extract)."""
    def __init__(self, attrs, *children):
        self.attrs = attrs
        super().__init__(*children)

    def params(self):
        return self.attrs

    def to_html(self, outf, indent=0):
        filler, filler1 = ' ' * indent, ' ' * (indent + 4)
        print(f'{filler}<html>', file=outf)
        print(f'{filler1}<head><title>{self.attrs["title"]}</title></head>',
              file=outf)
        print(f'{filler1}<body>', file=outf)
        super().to_html(outf, indent)
        print(f'{filler1}</body>\n{filler}</html>', file=outf)


class Section(Unit):
    """:class:`Unit` representing a section."""
    def __init__(self, title=None, level=None, *children):
        """
        :param title: the title of the section (the text of the `h*` tag)
        :param level: the number in the `h` tag
        """
        self.title = title
        self.level = level
        super().__init__(*children)

    def params(self):
        return {'title': self.title, 'level': self.level}

    def to_html(self, outf, indent=0):
        filler, filler1 = ' ' * indent, ' ' * (indent + 4)
        print(f'{filler}<section>', file=outf)
        print(f'{filler1}<h{self.level}>{self.title}</h{self.level}>', file=outf)
        super().to_html(outf, indent)
        print(f'{filler}</section>', file=outf)


class Paragraph(Unit):
    """:class:`Unit` representing a paragraph of text."""
    def to_html(self, outf, indent=0):
        filler, filler1 = ' ' * indent, ' ' * (indent + 4)
        print(f'{filler}<p>', file=outf)
        for line in self:
            print(f'{filler1}{line}', file=outf)
        print(f'{filler}</p>', file=outf)


class List(Unit):
    """:class:`Unit` representing an ordered or unordered list."""
    def __init__(self, ordered=False, *children):
        self.ordered = ordered
        super().__init__(*children)

    def to_html(self, outf, indent=0):
        filler, filler1, filler2 = (
            ' ' * indent, ' ' * (indent + 4), ' ' * (indent + 8))
        tag = 'ol' if self.ordered else 'ul'
        print(f'{filler}<{tag}>', file=outf)
        li_open = False
        for thing in self:
            if isinstance(thing, Unit):
                assert li_open
                thing.to_html(outf, indent + 8)
            else:
                if li_open:
                    print(f'{filler1}</li>', file=outf)
                print(f'{filler1}<li>', file=outf)
                print(f'{filler2}{thing}', file=outf)
                li_open = True
        else:
            if li_open:
                print(f'{filler1}</li>', file=outf)
        print(f'{filler}</{tag}>', file=outf)


def filter_tags(tag):
    """Enumerates the non-comment, non-newline children of _tag_."""
    for child in tag.children:
        if isinstance(child, Comment):
            continue
        elif isinstance(child, NavigableString) and child == '\n':
            continue
        else:
            yield child


def parse_li(li_tag):
    content = []
    children = []
    for child in filter_tags(li_tag):
        if isinstance(child, NavigableString):
            content.append(child)
        elif child.name == 'ul' or child.name == 'ol':
            children.append(parse_list(child))
        else:
            content.append(child.get_text())
    return [''.join(content).strip()] + children


def parse_list(lst_tag):
    lst = List(ordered=lst_tag.name == 'ol')
    for child in filter_tags(lst_tag):
        if isinstance(child, NavigableString):
            raise ValueError(f'Unexpected navigablestring in {lst_tag.name}')
        elif child.name != 'li':
            raise ValueError(f'Unexpected tag {child.name} in {lst_tag.name}')
        else:
            lst.extend(parse_li(child))
    return lst


def parse_section(section_tag):
    section = Section()
    # These two variables are needed to account for NavigableStrings between
    # <p>s. Might not be necessary actually.
    unpaired_strs = []
    last_p = None
    for child in filter_tags(section_tag):
        if isinstance(child, NavigableString):
            raise ValueError('NavigableString in section!')
            text = child.strip()
            if text:
                if last_p:
                    last_p.add(text)
                else:
                    unpaired_strs.append(text)
        elif child.name == 'section':
            section.add(parse_section(child))
        elif child.name == 'p':
            p = Paragraph()
            text = ' '.join(child.get_text().split())
            if unpaired_strs:
                for us in unpaired_strs:
                    p.add(us)
                unpaired_strs = []
            if text:
                p.add(text)
            if len(p):
                section.add(p)
                last_p = p
        elif child.name.startswith('h'):
            section.title = child.get_text()
            section.level = int(child.name[1:])
        elif child.name == 'ol' or child.name == 'ul':
            section.add(parse_list(child))
    return section


def parse_zim_html(html_text):
    """
    Parses the HTML text of a Wikipedia page. Due to the sorry state of the
    WP tooling, this is the only reliable way of extracting the text from
    a WP page.

    Of course, static HTML dumps are unsupported, so the only way of getting
    them is through the
    `Kiwix ZIM files <https://wiki.kiwix.org/wiki/Content_in_all_languages>`_.

    .. warning::
    Note that this code can only parse the HTML in the Kiwix ZIM archives. The
    exact structure, class names, ids, etc. are different from the HTML
    on wikipedia.org. Also, even some of the .zim files have differently
    structured HTMLs; however, the main Wikipedia dumps (_all_) should work.
    """
    bs = BeautifulSoup(html_text)
    title = bs.find(id='titleHeading')
    body = bs.find('div', id='mw-content-text')
    # Let's get rid of the references now
    for sup in body.find_all('sup', {'class': 'mw-ref'}):
        sup.decompose()
    page = WikiPage({'title': title.get_text()})
    for child in body.children:
        if child.name == 'section':
            page.add(parse_section(child))
    if len(page) > 0 and not page[0].title:  # most likely
        page[0].title = title.get_text()
        page[0].level = int(title.name[1:])

    return page


def enumerate_static_dump(static_dump_file: str) -> Generator[str, None, None]:
    """
    Reads the specified static Wikipedia HTML dump file (the output of
    :command:`zim_to_dir`) and enumerates all pages therein.
    """
    with gzip.open(static_dump_file, 'rb') as inf:
        for doc_no in count(1):
            size_raw = inf.read(4)
            if len(size_raw) != 4:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            elif not size_raw:
                break
            size = struct.unpack('!i', size_raw)[0]
            html_raw = inf.read(size)
            if len(html_raw) != size:
                raise EOFError(f'{static_dump_file} ended abruptly '
                               f'after {doc_no} documents.')
            html = html_raw.decode('utf-8')
            yield html
