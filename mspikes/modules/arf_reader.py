# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that reads data from an ARF file.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import h5py
from mspikes.types import DataBlock, RandomAccessSource

class arf_reader(RandomAccessSource):
    """Read data from an ARF/HDF5 file"""

    def __init__(self, filename, channels, **options):
        """Open an ARF file for reading.

        filename -- the path of the file to open
        channels -- list of channels to include
        times    -- [start,stop) times (in s, relative to start of file)
                    to include in iteration (default is all)
        entries  -- list of entries to include (default is all)

        """
        self.file = h5py.File(filename, "r")
        self.channels = channels
        self.times = options.get("times", None)
        self.entries = options.get("entries", None)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="list of channels",
                 metavar='CH',
                 nargs='+')
        addopt_f("--times",
                 help="range of times (in s) to analyze (default all)",
                 type=float,
                 metavar='FLOAT',
                 nargs=2)
        addopt_f("--entries",
                 help="list of entries to analyze (default all)",
                 metavar='E',
                 nargs="+")

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
        return super(arf_reader,self).targets


# Variables:
# End:
