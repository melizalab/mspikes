# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""
import sys
from mspikes import util
from mspikes.types import Node


class stream_sink(Node):
    """Output data block info to a stream"""

    def __init__(self, **options):
        util.set_option_attributes(self, options, stream=sys.stdout)

    @classmethod
    def options(cls, addopt_f, **defaults):
        from argparse import FileType
        addopt_f("file",
                 help="file for output (default stdout)",
                 nargs='?',
                 type=FileType('w'),
                 default=defaults.get('stream', sys.stdout))

    def send(self, chunk):
        # TODO better formatting
        print >> self.stream, chunk
        return chunk.offset

# Variables:
# End:
