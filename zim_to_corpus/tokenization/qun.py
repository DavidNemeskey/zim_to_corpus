#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wrapper for the quntoken tokenizer."""

from io import StringIO
import json
from typing import List
from urllib.parse import urlparse, urlunparse

import requests

from .core import Sentence, Tokenizer


class QunTokenizer(Tokenizer):
    """
    Uses ``quntoken`` via ``emtsv``.
    """
    def __init__(self, emtsv_url: str):
        """
        Creates the tokenizer.

        :param emtsv_url: the URL to the ``emtsv`` REST API.
        """
        scheme, netloc, *_ = urlparse(emtsv_url)
        self.emtsv_url = urlunparse((scheme, netloc, 'tok', '', '', ''))

    def __call__(self, text: str) -> List[Sentence]:
        """Tokenizes _text_ with quntoken."""
        r = requests.post(self.emtsv_url, data={'text': text})
        if not r.status_code == 200:
            raise RuntimeError(r.json()['message'])

        sentences = []
        for sentence_str in r.text.partition('\n')[2].split('\n\n'):
            sentences.append(self.get_sentence(sentence_str))
        return [s for s in sentences if s]

    @staticmethod
    def get_sentence(sentence_str: str) -> Sentence:
        """
        Extracts a :class:`Sentence` from output of Quntoken.

        :param sentence_str: the part of the tsv output that corresponds to
                             a single sentence.
        """
        tokens_and_spaces = [l.split('\t') for line in
                             sentence_str.split('\n') if (l := line.strip())]
        if len(tokens_and_spaces):
            text = StringIO()
            tokens = []
            for token, space in tokens_and_spaces:
                tokens.append(token)
                text.write(token)
                text.write(json.loads(space))
            return Sentence(text.getvalue().strip(), tokens)
        else:
            return None
