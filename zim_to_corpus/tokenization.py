#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wrappers for various tokenizers. Both the WT-2 and the BERT output formats
require sentence splitting or tokenization, hence the integrated support.

This package provides a simple whitespace tokenizer, as well as wrappers for
two proper, third-party tokenizers: spaCy and quntoken.
"""

import re
from typing import List

class Tokenizer:
    """Base class for all tokenizers / sentence splitters."""
    def __init__(self, split_sentences=True, tokenize=True):
        """
        Creates a :class:`Tokenizer` that can tokenize, split sentences, or both.

        :param split_sentences: whether to split sentences.
        :param tokenize: whether to perform tokenization.
        """
        self.do_split = split_sentences
        self.do_token = tokenize

    def tokenize(self, text: str) -> List[List[str]]:
        """
        Tokenizes _text_ and splits it into sentences.

        :param text: a regular string.
        :returns: a list of sentences, each a list of tokens. If sentence
                  splitting was not requested, the outer list will have only
                  a single item; if tokenization was not requested, the inner
                  lists.
        """
        if not (self.do_split or self.do_token):
            return [[text]]
        else:
            return self.do_tokenize(text)

    def do_tokenize(self, text: str) -> List[List[str]]:
        """
        Called by :meth:`tokenize`. Subclasses should override this method.
        Implementations can assume that at least one of the two tasks was
        actually requested (i.e. the tokenizer is not "dummy").
        """
        raise NotImplementedError(
            f'{self.__class__.__name__} must implement do_tokenize')


class WhitespaceTokenizer(Tokenizer):
    endp = re.compile('[.!?]$')

    def do_tokenize(self, text):
        tokens = text.split()
        sentences = []
        if self.do_split:
            sentence = []
            for token in tokens:
                sentence.append(token)
                if self.endp.search(token):
                    sentences.append(sentence)
                    sentence = []
            if sentence:
                sentences.append(sentence)
            if not self.do_token:
                sentences = [[' '.join(sentence)] for sentence in sentences]
        else:
            # No sentence splitting => tokenization was requested
            sentences.append(tokens)
        return sentences
