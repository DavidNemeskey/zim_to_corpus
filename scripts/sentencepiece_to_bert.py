#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converts a sentencepiece-style vocabulary file to BERT-style.
The script reads from stdin and writes to stdout.
"""

from argparse import ArgumentParser
import sys


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    return parser.parse_args()


def main():
    _ = parse_arguments()

    for line in sys.stdin:
        token = line.strip().split('\t')[0]
        if token.startswith('▁'):
            if len(token) > 1:
                print(token[1:])
        else:
            print(f'##{token}')


if __name__ == '__main__':
    main()
