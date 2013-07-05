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


def exponential_smoother(data, M, M_0=None, S_0=None):
    """Calculate moving first and second moments of data using an exponential smoother

    Given a time series X = {x_0,...,x_N}, calculates a weighted average of f(x_i) and the
    values of f(x_j) for j = {i - M, ... i - 1}, with the past values weighted by
    the number of samples (M), where f() is an arbitrary function of x.

    S_i = (S_{i-1} * M + f(x_i)) / (M + 1)

    The intial value S_0 can be estimated from the first M samples of X, or it can
    be supplied as a value along with the number of samples used to make the estimate.

    data - a 1-dimensional array
    M    - the number of samples to use in the integration window
    M_0  - the number of samples to use in initialization. If not supplied, M is used.

    S_0  - tuple giving initial estimates for (mean, variance). If not supplied, the values
           are estimated from the first M_0 samples of the data

    """
    from numpy import zeros
    assert data.ndim == 1
    avg = zeros(data.shape)
    var = zeros(data.shape)

    if M_0 is None or M_0 == 0:
        M_0 = M

    if S_0 is None or M_0 == 0:
        a_0, v_0 = (data[:M_0].mean(), data[:M_0].var())
    else:
        a_0, v_0 = S_0

    mean = lambda i, p, n: (p * n + data[i]) / (n + 1)
    variance = lambda i, p, n: (p * n + (data[i] - avg[i]) ** 2) / (n + 1)

    avg[0] = mean(0, a_0, M_0)
    var[0] = variance(0, v_0, M_0)

    # unrolled loop for different weightings
    i = 1
    for i in xrange(1, M_0):
        avg[i] = mean(i, avg[i-1], M_0)
        var[i] = variance(i, var[i-1], M_0)

    for i in xrange(i, M):
        avg[i] = mean(i, avg[i-1], i)
        var[i] = variance(i, var[i-1], i)

    for i in xrange(i, data.size):
        avg[i] = mean(i, avg[i-1], M)
        var[i] = variance(i, var[i-1], M)

    return avg, var


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
