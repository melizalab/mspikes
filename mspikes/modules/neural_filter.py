# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
from __future__ import division
import logging
from mspikes.types import Source, Sink, DataBlock

_log = logging.getLogger(__name__)


def exponential_smoother(data, window_size, init=None):
    """Calculate moving window statistics of data using an exponential smoother

    window_size - the integration window
    init - a tuple giving (initial value, number of points) for initializing the
           smoother. If not supplied, the first window_size points will be used.
    """

    from numpy import zeros
    assert data.ndim == 1
    avg = zeros(data.shape)

    if init is None:
        init = data[:window_size].mean()
        N = window_size
    else:
        init, N = init

    avg[0] = (init * N + data[0]) / (N + 1)

    i = 1
    while i < N:
        avg[i] = (avg[i-1] * N + data[i]) / (N + 1)
        i += 1

    while i < window_size:
        avg[i] = (avg[i-1] * i + data[i]) / (i + 1)
        i += 1

    while i < data.size:
        avg[i] = (avg[i-1] * window_size + data[i]) / (window_size + 1)
        i += 1

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
