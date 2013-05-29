# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that generates random data

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""

from ..types import data_chunk, Source


class random_source(Source):

    def __init__(self, options):
        self.chunk_size = 1024
        self.channel = "random"
        self.sampling_rate = 1
        self.seed = options.seed

    @classmethod
    def descr(cls):
        return "Generate random data"

    @classmethod
    def options(cls, arggroup):
        arggroup.add_argument("seed",
                              help="seed for random number generator",
                              type=float,
                              default=1.0)

    def __iter__(self):
        from numpy import RandomState
        from itertools import count
        randg = RandomState(self.seed)
        return (data_chunk(self.channel,
                           i*self.chunk_size,
                           self.sampling_rate,
                           randg.randn(1024))
                for i in count(0))

# Variables:
# End:
