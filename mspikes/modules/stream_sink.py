# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Sink that outputs information about chunks to the console.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:06:22 2013
"""
from mspikes.types import Sink


class stream_sink(Sink):

    def __init__(self, **options):
        for opt in ("stream"):
            if options.has_key(opt): setattr(self, opt, options[opt])

    @classmethod
    def descr(cls):
        return "Output data information to a stream"

    @classmethod
    def options(cls, arggroup, prefix):
        from sys import stdout
        from argparse import FileType
        arggroup.add_argument("{}-stream".format(prefix),
                              help="file for output (default stdout)",
                              type=FileType('w'),
                              default=stdout)

    def __call__(self, chunk):
        # TODO better formatting
        print >> self.fp, chunk

# Variables:
# End:
