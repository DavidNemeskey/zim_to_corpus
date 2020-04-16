#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generates a vocabulary from a (BERT-style) text corpus via the sentencepiece
Python package. All files in the corpus must be in the .gz format.
"""

from argparse import ArgumentParser
import logging
from multiprocessing import Process
import os
import resource
import time

from multiprocessing_logging import install_mp_handler


def parse_arguments():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', '-i', required=True, action='append',
                        help='an input directory / file. Can be specified '
                             'more than once.')
    parser.add_argument('--output', '-o', required=True,
                        help='the output prefix of the model/vocabulary.')
    parser.add_argument('--sample-ratio', '-s', type=float, default=1.0,
                        help='what ratio of input lines to process. Note that '
                             'sentencepiece reads all input lines into memory, '
                             'so depending on the corpus size, the ratio '
                             'should be lowered from the default 1.0.')
    parser.add_argument('--model', '-m', required=True,
                        choices=['bpe', 'unigram'],
                        help='the algorithm to run.')
    parser.add_argument('--vocabulary-size', '-v', type=int, required=True,
                        help='the vocabulary size.')
    parser.add_argument('--character-coverage', '-c', type=float, default=1.0,
                        help='the character coverage. The default is 1.0.')
    parser.add_argument('--extra-arguments', '-e', default='',
                        help='specify extra options to the sentencepiece '
                             'algorithms not covered by the other arguments.')
    parser.add_argument('--log-level', '-L', type=str, default='info',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='the logging level.')
    args = parser.parse_args()

    try:
        import sentencepiece as spm  # noqa
    except ImportError:
        parser.error('The sentencepiece Python package is not available. '
                     'Please install it before runing the script.')

    return args


def pipe_inputs_into_fifo(inputs, fifo, sample_ratio):
    pipe_inputs = []
    for input in inputs:
        if os.path.isfile(input):
            pipe_inputs.append(input)
        elif os.path.isdir(input):
            pipe_inputs.append(f'{input}/*.gz')
        else:
            logging.error('Input {input} is not a valid file or directory.')
    logging.debug(f'Piping process started with inputs {pipe_inputs}.')
    os.system(f'zcat {" ".join(pipe_inputs)} | perl -ne '
              f'"print if (rand() < {sample_ratio})" > {fifo}')

def train(inputs, prefix, sample_ratio, model, vocab_size, char_coverage):
    import sentencepiece as spm

    model_prefix = f'{prefix}_{model}_{vocab_size}_{char_coverage}'
    fifo_path = f'{model_prefix}.fifo'
    proc = Process(target=pipe_inputs_into_fifo,
                   args=[inputs, fifo_path, sample_ratio])
    try:
        logging.info(f'Creating FIFO {fifo_path}...')
        os.mkfifo(fifo_path)
        logging.debug('Starting process...')
        proc.start()
        logging.debug('Process started.')
        st = time.time()

        args = (f'--input={fifo_path} --model_prefix={model_prefix} '
                f'--vocab_size={vocab_size} --model_type={model} '
                f'--character_coverage={char_coverage} '
                f'--normalization_rule_name=identity')
        logging.info(f'args {args}')
        spm.SentencePieceTrainer.Train(
            f'--input={fifo_path} --model_prefix={model_prefix} '
            f'--vocab_size={vocab_size} --model_type={model} '
            f'--character_coverage={char_coverage} '
            f'--normalization_rule_name=identity'
        )
        r = resource.getrusage(resource.RUSAGE_SELF)
        logging.info(f'Took {time.time() - st} seconds for {model} '
                     f'{vocab_size}, using {r.ru_maxrss / 1024:.2f}M memory')
    except:
        logging.exception('Error')
    finally:
        try:
            os.remove(fifo_path)
            proc.join(1)
            if proc.is_alive():
                proc.terminate()
            logging.debug(f'Piping process exited with exit '
                          f'code {proc.exitcode}.')
        except FileNotFoundError:
            pass


def main():
    args = parse_arguments()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(process)s - %(levelname)s - %(message)s'
    )
    install_mp_handler()

    logging.info(f'Script: {__file__}, args: {args}')

    train(args.inputs, args.output, args.sample_ratio,
          args.model, args.vocabulary_size, args.character_coverage)


if __name__ == '__main__':
    main()
