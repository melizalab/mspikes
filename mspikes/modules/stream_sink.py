# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""
import sys
from mspikes.types import Sink


class stream_sink(Sink):
    """Output data block info to a stream"""

    stream = sys.stdout

    def __init__(self, **options):
        for opt in ("stream"):
            if options.has_key(opt): setattr(self, opt, options[opt])

    @classmethod
    def options(cls, addopt_f, **defaults):
        from argparse import FileType
        addopt_f("file",
                 help="file for output (default stdout)",
                 nargs='?',
                 type=FileType('w'),
                 default=defaults.get('stream',cls.stream))

    def recv(self, chunk):
        # TODO better formatting
        print >> self.stream, chunk
        return chunk.offset

# Variables:
# End:
