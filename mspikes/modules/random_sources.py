# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Sources of random data

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""

from mspikes.types import DataBlock, IterableSource
from numpy.random import RandomState


class rand_samples(IterableSource):
    """Generates random values from N(0,1)"""
    seed = 1
    nsamples = 4096

    def __init__(self, **options):
        # boilerplate
        for opt in ("seed","nsamples"):
            if options.has_key(opt): setattr(self, opt, options[opt])
        self.chunk_size = 1024
        self.channel = "random"
        self.sampling_rate = 1
        self._randg = RandomState(self.seed)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--seed",
               help="seed for random number generator",
               type=int,
               metavar='INT',
               default=defaults.get('seed',cls.seed))
        addopt_f("--nsamples",
               help="number of samples to generate",
               type=int,
               metavar='INT',
               default=defaults.get('nsamples',cls.nsamples))

    def data(self, t=0):
        """Generates a data chunk"""
        return DataBlock(id=self.channel, repr=0, offset=t, dt=self.sampling_rate,
                         data=self._randg.randn(self.chunk_size))

    def __iter__(self):
        t = 0
        while t < self.nsamples:
            yield self.send(self.data(t))
            t += self.chunk_size

## TODO random_events

# Variables:
# End:
