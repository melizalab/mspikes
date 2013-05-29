# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""

from ..types import Sink


class debug_sink(Sink):

    def __init__(self, options):
        self.fp = options.output_stream

    @classmethod
    def descr(cls):
        return "Output debug information to a stream"

    @classmethod
    def options(cls, arggroup):
        from sys import stdout
        from argparse import FileType
        arggroup.add_argument("output-stream",
                              help="file or stream for output",
                              type=FileType('w'),
                              default=stdout)

    def push(self, chunk):
        print >> self.fp, chunk

# Variables:
# End:
