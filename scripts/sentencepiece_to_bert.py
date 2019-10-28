#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converts a sentencepiece-style vocabulary file to BERT-style.
The script reads from stdin and writes to stdout.
"""

from argparse import ArgumentParser
import sys


# BERT tags to add to the vocabulary
bert_tags = ['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[MASK]']
# sentencepiece tags to remove from vocabulary
spm_tags = {'<unk>', '<s>', '</s>'}


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--unused-tokens', '-u', type=int, default=1000,
                        help='the number of [unusedXX] tokens. '
                             'The default is 1000.')
    return parser.parse_args()


def main():
    args = parse_arguments()

    for tag in bert_tags:
        print(tag)
    for unused in range(1, args.unused_tokens + 1):
        print(f'[unused{unused}]')
    for line in sys.stdin:
        token = line.strip().split('\t')[0]
        if token in spm_tags:
            continue
        if token.startswith('▁'):
            if len(token) > 1:
                print(token[1:])
        else:
            print(f'##{token}')


if __name__ == '__main__':
    main()
