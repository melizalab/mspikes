# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""
import sys
from mspikes.types import Sink


class stream_sink(Sink):

    stream = sys.stdout

    def __init__(self, **options):
        for opt in ("stream"):
            if options.has_key(opt): setattr(self, opt, options[opt])

    @classmethod
    def descr(cls):
        return "Output data information to a stream"

    @classmethod
    def options(cls, arggroup, prefix, **defaults):
        from argparse import FileType
        arggroup.add_argument("{}-file".format(prefix),
                              help="file for output (default stdout)",
                              nargs='?',
                              type=FileType('w'),
                              default=defaults.get('stream',cls.stream))

    def __call__(self, chunk):
        # TODO better formatting
        print >> self.stream, chunk
        return chunk.time

# Variables:
# End:
