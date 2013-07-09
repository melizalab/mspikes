# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
from __future__ import division
import logging

from mspikes import util
from mspikes.types import Node, DataBlock

_log = logging.getLogger(__name__)

def moving_meanvar(x, s, w):
    """Calculating moving mean and variance of a time series

    x - input data. 1-dimensional numpy array

    s - previous state: (mean, variance)

    w - weight assigned to previous state, relative to the number of elements in
        x. set to 0 to initialize

    returns updated mean, variance

    """
    m = (s[0] * w + x.sum()) / (w + x.size)
    v = (s[1] * w + ((x - m) ** 2).sum()) / (w + x.size)
    return (m, v)


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

    # initial values from data
    if S_0 is None:
        S_0 = moving_meanvar(data[:M_0], (0, 0), 0)

    # unrolled loop for different weightings
    for i in xrange(0, M_0, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, M_0)
        yield S_0

    for i in xrange(M_0, M, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, i+1)
        yield S_0

    for i in xrange(M, data.size, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, M)
        yield S_0


class rms_exclude(Node):
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

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--window",
                 help="integration window for calculating RMS (in min; default %(default).1f)",
                 default=defaults.get('window', 1),
                 type=float,
                 metavar='FLOAT')




class zscale(Node):
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
                 help="duration of sliding window for calculating mean and SD (in s; default %(default).1f)",
                 default=defaults.get('window', 2),
                 type=float,
                 metavar='SEC')
        addopt_f("--step",
                 help="step size for sliding window (in ms; default=%(default).1f)",
                 default=defaults.get('step', 100),
                 type=float,
                 metavar='MS')
        addopt_f("--exclude-rms",
                 help="if set, exclude intervals where RMS is greater than %(metavar)s %% above baseline",
                 type=float,
                 metavar='FLOAT')




    def __init__(self, **options):
        util.set_option_attributes(self, options, window=2.0)

    def send(self, data):
        pass



# Variables:
# End:
