# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that generates random data

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""

from mspikes.types import DataBlock, IterableSource

class rand_samples(IterableSource):
    """Generates random values from N(0,1)

    This Source is useful for testing and not much else.

    """

    seed = 1
    nsamples = 4096

    def __init__(self, **options):
        # boilerplate
        for opt in ("seed","nsamples"):
            if options.has_key(opt): setattr(self, opt, options[opt])
        self.chunk_size = 1024
        self.channel = "random"
        self.sampling_rate = 1
        self._targets = []

    @classmethod
    def options(cls, arggroup, prefix, **defaults):
        arggroup.add_argument("--{}-seed".format(prefix),
                              help="seed for random number generator",
                              type=int,
                              metavar='INT',
                              default=defaults.get('seed',cls.seed))
        arggroup.add_argument("--{}-nsamples".format(prefix),
                              help="number of samples to generate",
                              type=int,
                              metavar='INT',
                              default=defaults.get('nsamples',cls.nsamples))

    def __iter__(self):
        from numpy.random import RandomState
        randg = RandomState(self.seed)
        t = 0
        while t < self.nsamples:
            data = DataBlock(self.channel, t, self.sampling_rate, randg.randn(self.chunk_size))
            yield [tgt(data) for tgt,filt in self.targets if filt(data)]
            t += self.chunk_size

    @property
    def targets(self):
        return super(random_samples,self).targets

## TODO random_events

# Variables:
# End:
