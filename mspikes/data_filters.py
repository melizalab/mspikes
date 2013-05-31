# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions to filter data chunks.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Fri May 31 13:19:05 2013
"""

def event(chunk):
    """Return True if the chunk contains event data"""
    # compound datatypes or real timebases can only be events
    return (chunk.data.dtype.names is not None or
            getattr(chunk, 'sampling_rate', None) is None)

def sampled(chunk):
    """Return True if the chunk contains sampled data"""
    # only two types defined right now
    return not event(chunk)


# Variables:
# End:
