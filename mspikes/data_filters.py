# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions to filter data chunks.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Fri May 31 13:19:05 2013
"""


def event(chunk):
    """True if the chunk contains event (point process) data"""
    # compound datatypes or real timebases can only be events
    return (hasattr(chunk.data, "dtype") and
            getattr(chunk.data.dtype, "names", None) is not None)


def sampled(chunk):
    """True if the chunk contains sampled (time-series) data"""
    return (hasattr(chunk.data, "dtype") and
            getattr(chunk.data.dtype, "names", None) is None)


# Variables:
# End:
