# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that reads data from an ARF file.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import arf
from mspikes import util
from mspikes.types import DataBlock, RandomAccessSource

def true_p(*args): return True

class arf_reader(RandomAccessSource):
    """Read data from an ARF/HDF5 file"""

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="names or regexps of channels (default all)",
                 metavar='CH',
                 nargs='+')
        addopt_f("--times",
                 help="range of times (in s) to analyze (default all)",
                 type=float,
                 metavar='FLOAT',
                 nargs=2)
        addopt_f("--entries",
                 help="names or regexps of entries (default all)",
                 metavar='P',
                 nargs="+")

    def __init__(self, filename, **options):
        import re
        self.file = arf.file(filename, "r")
        self.times = options.get("times", None)

        if "channels" in options:
            rx = (re.compile(p).search for p in options['channels'])
            self.chanp = util.chain_predicates(*rx)
        else:
            self.chanp = true_p

        if "entries" in options:
            rx = (re.compile(p).search for p in options['entries'])
            self.entryp = util.chain_predicates(*rx)
        else:
            self.entryp = true_p


    def _entry_table(self):
        """ Generate a table of entries and start times """
        from itertools import ifilter

        # choose an entry key function based on file creator

        it = ifilter(self.entryp, self.file)



    def __iter__(self):
        # questions about how to iterate:
        #
        # 1. does it matter what order we go through entries? Yes for some
        # applications but not for others. Sorting takes time though because we
        # have to load all the entries and inspect the timestamp attributes (or
        # some other key.
        #
        # 2. validate whether the requested channels are homogeneous across
        # entries? probably not, it's rather pathological if they're not
        #
        # 3. How about whether there's overlapping data?  Okay with the arf
        # spec, but do we try to straighten it out?  How to detect?  Need to
        # keep track of whether the time has passed the start time of the next entry
        #
        # 4. dealing with different timebases and formats. Some arf files will
        # have sample counts, which should probably be used instead of
        # timestamps when possible...


        pass

# Variables:
# End:
