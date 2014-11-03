#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Eric Kow
# License: BSD3

"""
Augment attelo .conll output with some EDU info
"""

from __future__ import print_function
import argparse
import csv
import os
import sys

from educe.annotation import Span
from educe.stac.learning import features
import educe.corpus
import educe.learning.keys
import educe.glozz
import educe.stac
import educe.util


NAME = 'weave'


def _read_unannotated_corpus(args):
    """
    Read only the unannotated parts of a corpus
    """
    args.stage = 'unannotated'
    is_interesting = educe.util.mk_is_interesting(args)
    reader = educe.stac.Reader(args.corpus)
    anno_files = reader.filter(reader.files(), is_interesting)
    return reader.slurp(anno_files)


def _read_conll(instream):
    """
    Iterator for an attelo conll file
    """
    return csv.reader(instream, dialect=csv.excel_tab)


def _write_conll(outstream, rows):
    """
    Writer from the given iterator to the output stream
    """
    writer = csv.writer(outstream, dialect=csv.excel_tab)
    for row in rows:
        writer.writerow(row)


def _dialogue_map(corpus):
    """
    Return a dictionary mapping 'friendly' dialogue ids that we would
    have given to attelo (via feature extraction) to the actual
    documents
    """
    dialogues = {}
    for key in corpus:
        doc = corpus[key]
        for anno in filter(educe.stac.is_dialogue, doc.units):
            anno_id = features.friendly_dialogue_id(key, anno.text_span())
            dialogues[anno_id] = (doc, anno.identifier())
    return dialogues


def _tweak_row(dialogues, row):
    """
    Adjust a CONLL row to taste
    """
    [anno_id, group_id, start, end] = row[:4]
    suffix = row[4:]
    span = Span(int(float(start)),
                int(float(end)))
    doc, _ = dialogues[group_id]
    prefix2 = [anno_id,
               #group_id,
               doc.text(span).encode('utf-8'),
               span.char_start,
               span.char_end]
    return prefix2 + suffix


# ----------------------------------------------------------------------
# options
# ----------------------------------------------------------------------


def config_argparser(parser):
    """
    Subcommand flags.
    """
    parser.add_argument('corpus', metavar='DIR',
                        help='Corpus dir (eg. data/pilot)')
    parser.add_argument('input', nargs='?', type=argparse.FileType('rb'),
                        default=sys.stdin)
    parser.add_argument('--output', nargs='?', type=argparse.FileType('wb'),
                        default=sys.stdout)
    parser.set_defaults(func=main)

# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------


def main(args):
    "main"

    corpus = _read_unannotated_corpus(args)
    dialogues = _dialogue_map(corpus)
    conll = _read_conll(args.input)
    revised = (_tweak_row(dialogues, r) for r in conll)
    _write_conll(args.output, revised)