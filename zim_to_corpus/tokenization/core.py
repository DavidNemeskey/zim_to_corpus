#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The two basic tokenizers + the common infrastructure.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
import re
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

    def tokenize(self, text: str, sentence_delim=' ') -> str:
        """
        Tokenizes _text_ into a single string.

        :param text: the string to tokenize.
        :param sentence_delim: the delimiter to put between two sentences.
        :returns: a string in which the tokens of a sentence are separated by
                  a space, and sentences are separated by _sentence_delim_.
        """
        return sentence_delim.join(' '.join(sent.tokens) for sent in self(text))

    def ssplit(self, text: str, sentence_delim='\n') -> str:
        """
        Returns a string in which sentences are separated by _sentence_delim_.

        :param text: the string to tokenize.
        :param sentence_delim: the delimiter to put between two sentences.
        :returns: a string in which the raw text sentences are separated by
                  _sentence_delim_.
        """
        return sentence_delim.join(sent.text for sent in self(text))


class DummyTokenizer(Tokenizer):
    """Does nothing."""
    def __call__(self, text: str) -> List[Sentence]:
        return [Sentence(text, text)]


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
