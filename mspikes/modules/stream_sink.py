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
    """Output data block info to the console"""

    def __init__(self, **options):
        self.stream = sys.stdout

    def send(self, chunk):
        # TODO better formatting
        print >> self.stream, chunk
        return chunk.offset

# Variables:
# End:
