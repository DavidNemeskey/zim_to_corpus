#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wrappers for various tokenizers. Both the WT-2 and the BERT output formats
require sentence splitting or tokenization, hence the integrated support.

This package provides a simple whitespace tokenizer, as well as wrappers for
two proper, third-party tokenizers: spaCy and quntoken.
"""

from .core import DummyTokenizer, Sentence, Tokenizer, WhitespaceTokenizer  # noqa
