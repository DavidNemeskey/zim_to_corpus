#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wrapper for the quntoken tokenizer."""

import re
import sys
from typing import List

from .core import Sentence, Tokenizer


class QunTokenizer(Tokenizer):
    """
    Uses the quntoken library.

    .. note::
    The Python bindings for quntoken are not available via Pypi, but are
    compiled with the rest of the library. So in order to use it, the path to
    the library must be provided to this wrapper.
    """
    # Regex to extract a sentence from quntoken's output
    senp = re.compile(r'<s>(.+?)</s>', re.S)
    # Regex to enumerate the XML tags from the sentence in quntoken's output
    tagp = re.compile(r'<(ws?|c)>(.+?)</\1>', re.S)

    def __init__(self, path):
        """
        Creates the tokenizer.

        :param path: path to the quntoken Python wrapper (``lib`` directory).
        """
        try:
            sys.path.insert(1, path)
            from quntoken import QunToken
            self.qt = QunToken('xml', 'token', False)
        except ImportError:
            raise ImportError(
                'quntoken is not available at {path}. Download and install '
                'from https://github.com/DavidNemeskey/quntoken/tree/v1'
            )

    def __call__(self, text: str) -> List[Sentence]:
        tokenized = self.qt.tokenize(text)
        sentences = []
        for m in self.senp.finditer(tokenized):
            sent = m.group(1)
            sentences.append(Sentence(self.get_text(sent), self.get_tokens(sent)))
        return sentences

    def get_text(self, xml_text: str) -> str:
        """
        Extracts the original text from the quntoken output.

        :param xml_text: the XML output from quntoken.
        """
        return ''.join(m.group(2) for m in self.tagp.finditer(xml_text))

    def get_tokens(self, xml_text: str) -> List[str]:
        """
        Extracts all tokens (non-whitespace units) from the quntoken output.

        :param xml_text: the XML output from quntoken.
        """
        return [m.group(2) for m in self.tagp.finditer(xml_text)
                if m.group(1) != 'ws']
