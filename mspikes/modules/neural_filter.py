# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
import logging
from mspikes.types import Source, Sink, DataBlock

_log = logging.getLogger(__name__)


def exponential_smoother(data, blocksize):
    from numpy import zeros
    assert data.ndim == 1
    avg = zeros(data.shape)
    avg[:blocksize] = data[:blocksize].mean()
    for i in xrange(blocksize, data.size):
        avg[i] = (avg[i-1] * blocksize + data[i]) / (blocksize + 1)

    return avg

def adaptive_exponential_smoother(data, blocksize, initsize=1):
    from numpy import zeros
    assert data.ndim == 1

    avg = zeros(data.shape)
    nframes = initsize
    avg[0] = data[:nframes].mean()
    for i in xrange(1, data.size):
        avg[i] = (avg[i - 1] * nframes + data[i]) / (nframes + 1)
        nframes = max(blocksize, max(nframes, i) + 1)

    return avg



class zscale(Source, Sink):
    """Centers and rescales time series data, optionally excluding

    accepts: all block types

    emits: z-scaled time-series blocks
           unmodified event and structure blocks
           start and stop exclusions (events)

    """

    pass



# Variables:
# End:
