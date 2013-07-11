# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Sources of random data

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""

from mspikes import util
from mspikes.types import DataBlock, Source, Node, tag_set
from numpy.random import RandomState


class rand_samples(Source):
    """Generates random values from N(0,1)"""
    seed = 1
    nsamples = 4096

    def __init__(self, **options):
        util.set_option_attributes(self, options, seed=1, nsamples=4096)
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
        return DataBlock(id=self.channel, offset=t, ds=self.sampling_rate,
                         data=self._randg.randn(self.chunk_size),
                         tags=tag_set("samples"))

    def __iter__(self):
        t = 0
        while t < self.nsamples:
            data = self.data(t)
            Node.send(self, data)
            yield data
            t += self.chunk_size

## TODO random_events

# Variables:
# End:
