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


def exponential_smoother(data, M, step=1, M_0=None, S_0=None):
    """Calculate moving first and second moments of data using an exponential smoother

    Given a time series X = {x_0,...,x_N}, calculates a weighted average of f(x_i) and the
    values of f(x_j) for j = {i - M, ... i - 1}, with the past values weighted by
    the number of samples (M), where f() is an arbitrary function of x.

    S_i = (S_{i-1} * M + f(x_i)) / (M + 1)

    The intial value S_0 can be estimated from the first M samples of X, or it can
    be supplied as a value along with the number of samples used to make the estimate.

    data - a 1-dimensional array

    M    - the number of samples to use in the integration window

    step - the number of samples to advance the window. setting this to a value
           other than 1 (the default) means the data will be reduced by a factor
           of <step>.

    M_0  - the number of samples to use in initialization. If not supplied, M is used.

    S_0 - initial estimates for (mean, variance). If not supplied, the values
           are estimated from the first M_0 samples of the data

    """
    from numpy import zeros, array, asarray
    assert data.ndim == 1

    if M_0 is None or M_0 == 0:
        M_0 = M

    # initial values
    if S_0 is None:
        S = array((data[:M_0].mean(), data[:M_0].var()))
    else:
        S = asarray(S_0)

    def meanvar(i, n):
        x = data[i:i+step]
        S[0] = (S[0] * n + x.sum()) / (n + x.size)
        S[1] = (S[1] * n + ((x - S[0]) ** 2).sum()) / (n + x.size)
        return S

    # unrolled loop for different weightings
    i = 0
    for i in xrange(0, M_0, step):
        yield meanvar(i, M_0)

    for i in xrange(M_0, M, step):
        yield meanvar(i, i+1)

    for i in xrange(M, data.size, step):
        yield meanvar(i, M)


class rms_exclude(Source, Sink):
    """Exclude intervals when power exceeds a threshold.

    Movement artifacts are characterized by large transient increases in signal
    power and intervals with strong artifacts should be excluded from spike
    detection or clustering. Power may vary across channels and on slow
    timescales (minutes), so this module estimates power using a long-window
    moving average, and marks intervals for exclusion that deviate from this
    average by too much for too long.

    This algorithm is primiarily designed for single channels. For multiple
    electrodes, it may be more effective to remove artifacts by subtracting a
    common average reference.

    """
    pass



class zscale(Source, Sink):
    """Centers and rescales time series data using a sliding window

    Data are z-scaled by subtracting the mean and dividing by the standard
    deviation. The mean and SD of the data are calculated using a moving
    exponential smoother.

    accepts: all block types

    emits: z-scaled time-series blocks (_samples)
           unmodified _events and _structure blocks
           start and stop exclusions (_events)

    """

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--window",
                 help="integration window for calculating mean and SD (in s; default %(default).1f)",
                 default=2.0,
                 type=float,
                 metavar='FLOAT')



# Variables:
# End:
