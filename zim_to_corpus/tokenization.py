#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wrappers for various tokenizers. Both the WT-2 and the BERT output formats
require sentence splitting or tokenization, hence the integrated support.

This package provides a simple whitespace tokenizer, as well as wrappers for
two proper, third-party tokenizers: spaCy and quntoken.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
import re
import sys
from typing import List


# For holding both the raw and tokenized versions of a sentence
Sentence = namedtuple('Sentence', ['text', 'tokens'])


class Tokenizer(ABC):
    """Base class for all tokenizers / sentence splitters."""
    @abstractmethod
    def __call__(self, text: str) -> List[Sentence]:
        """
        Tokenizes _text_ and splits it into sentences.

        :param text: a regular string.
        :returns: a list of sentences.
        """
        ...


class WhitespaceTokenizer(Tokenizer):
    """
    A very simple tokenizer that splits tokens on whitespaces and sentences on
    the characters '.', '!' and '?'.
    """
    # Simplistic sentence end recognizer pattern
    endp = re.compile('[.!?]$')

    def __call__(self, text: str) -> List[Sentence]:
        tokens = text.split()
        sentences = []
        sentence = []
        for token in tokens:
            sentence.append(token)
            if self.endp.search(token):
                sentences.append(Sentence(' '.join(sentence), sentence))
                sentence = []
        if sentence:
            sentences.append(Sentence(' '.join(sentence), sentence))
        return sentences


class SpacyTokenizer(Tokenizer):
    """Uses spaCy to tokenize text."""
    def __init__(self, model: str, use_parser: bool = False,
                 *args: bool, **kwargs: bool):
        """
        Creates the tokenizer.

        :param model: name of the spaCy model to use.
        :param use_parser: if ``False`` (the default), use the ``sentencizer``
                           component instead of ``parser`` for sentence boundary
                           detection. It is faster, but probably less robust.
        :param args: forwarded to :meth:`Tokenizer.__init__`.
        :param kwargs: forwarded to :meth:`Tokenizer.__init__`.
        """
        super().__init__(*args, **kwargs)
        try:
            import spacy

            # Raises OSError if model is not available
            self.nlp = spacy.load(model)
            self.nlp.disable_pipes('tagger', 'ner')
            if not use_parser:
                self.nlp.add_pipe(self.nlp.create_pipe('sentencizer'))
                self.nlp.disable_pipes('parser')
        except ImportError:
            raise ImportError('spaCy is not available. Install it by e.g. '
                              'pip install -r requirements.txt')
        except OSError:
            raise OSError(f'Model {model} is not available. Install it by '
                          f'e.g. python -m spacy download {model}')

    def __call__(self, text: str) -> List[Sentence]:
        doc = self.nlp(text)
        return [
            Sentence(sent.text_with_ws.strip(), [str(t) for t in sent])
            for sent in doc.sents
        ]


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
                'quntoken is not available. Download and install '
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
