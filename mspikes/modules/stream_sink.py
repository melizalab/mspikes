# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""

from mspikes.types import Sink

class stream_sink(Sink):

    def __init__(self, options):
        self.fp = options.output_stream

    @classmethod
    def descr(cls):
        return "Output debug information to a stream"

    @classmethod
    def options(cls, arggroup, prefix):
        from sys import stdout
        from argparse import FileType
        arggroup.add_argument("{}-stream".format(prefix),
                              help="file or stream for output",
                              type=FileType('w'),
                              default=stdout)

    def push(self, chunk):
        # TODO better formatting
        print >> self.fp, chunk

# Variables:
# End:
