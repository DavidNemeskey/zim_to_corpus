#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Wrapper for the spaCy tokenizer."""

import logging
from typing import List

from .core import Sentence, Tokenizer


# Tokens that should no be split
special_cases = {
    'en': ['a.k.a.', '!Kora', '!Kung', '!Oka', '!PAUS3', '!T.O.O.H.!', '!Women',
           '!Wowow!', '!Hero!', '!HERO', '!Arriba!', '!Action']
}


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
            for lang, cases in special_cases.items():
                if model.startswith(lang):
                    from spacy.symbols import ORTH
                    for case in cases:
                        exception = [{ORTH: case}]
                        self.nlp.tokenizer.add_special_case(case, exception)
                    logging.debug(f'Added {len(cases)} special cases.')
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
