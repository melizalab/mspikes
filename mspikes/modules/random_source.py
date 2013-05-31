# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that generates random data

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""

from mspikes.types import data_chunk, IterableSource

class random_source(IterableSource):

    def __init__(self, options):
        self.chunk_size = 1024
        self.channel = "random"
        self.sampling_rate = 1
        self.seed = options.seed
        self.nsamples = options.nsamples
        self._targets = []

    @classmethod
    def descr(cls):
        return "Generate random values from N(0,1)"

    @classmethod
    def options(cls, arggroup, prefix):
        arggroup.add_argument("--{}-seed".format(prefix),
                              help="seed for random number generator",
                              type=int,
                              metavar='INT',
                              default=1)
        arggroup.add_argument("--{}-nsamples".format(prefix),
                              help="number of samples to generate",
                              type=int,
                              metavar='INT',
                              default=4096)


    def __iter__(self):
        from numpy.random import RandomState
        randg = RandomState(self.seed)
        t = 0
        while t < self.nsamples:
            data = data_chunk(self.channel, t, self.sampling_rate, randg.randn(self.chunk_size))
            yield (tgt(data) for tgt,filt in self.targets if filt(data))
            t += self.chunk_size

    @property
    def targets(self):
        return super(random_source,self).targets

# Variables:
# End:
