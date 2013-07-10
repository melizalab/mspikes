# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
from __future__ import division
import logging
import numpy as nx
from fractions import Fraction

from mspikes import util
from mspikes.types import Node, DataBlock
from mspikes.modules.util import coroutine

_log = logging.getLogger(__name__)

def moving_meanvar(x, w=0, s=None):
    """Calculating moving mean and variance of a time series

    x - input data. 1-dimensional numpy array

    w - weight assigned to previous state, relative to the number of elements in
        x. set to 0 to initialize

    s - previous state: (mean, variance)

    returns updated mean, variance

    """
    m0,v0 = (w * a for a in s) if w > 0 else (0, 0)
    m = (m0 + x.sum()) / (w + x.size)
    v = (v0 + ((x - m) ** 2).sum()) / (w + x.size)
    return (m, v)


class smoother(object):
    """A class for applying a moving smoother to data arrays

    Given a time series X = {x_0,...,x_N}, calculates the average of
    func({x_i,...,x_i+N}) and func({x_i-M,...x_i-1}), weighted by N and M.

    func -- a function with signature f(X, S, M) that updates the sliding window
            statistics according to the following formula:

            (S * M + f(X)) / (M + X.size)

    M -- the number of samples in the sliding window

    S0 -- the initial value of the smoother. If None, this will be estimated
          from the first M samples.

    N -- the number of samples used to calculate S0

    Usage:
    >>> g = smoother(mean, 100)
    >>> g.send(ones(50))
    None  # returns None until the number of samples is >= M
    >>> g.send(zeros(50))
    0.5
    >>> g.send(ones(1))
    0.504950495049505

    """

    def __init__(self, func, M):
        self.func = func
        self.size = M
        self.nsamples = 0
        self.state = None
        self.queue = []

    def send(self, chunk):

        self.nsamples += chunk.data.size

        if self.nsamples < self.size:
            queue.append(chunk)
            return None






@coroutine
def smoother(func, M, S0=None, N0=0):
    from numpy import concatenate, asarray

    queue = [()]
    N = N0
    try:
        while N < M:
            # return None while initializing
            X = asarray((yield))
            queue.append(X)
            N += X.size
        # calculate initial state from full length of the window
        X = concatenate(queue)
        S = func(X, N0, S0)
        while True:
            # note: send() assigns value to X, then loops and returns S
            X = asarray((yield S))
            S = func(X, M, S)
    except GeneratorExit:
        return


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
    assert data.ndim == 1

    if M_0 is None or M_0 == 0:
        M_0 = min(M, data.size)

    # initial values from data
    if S_0 is None:
        S_0 = moving_meanvar(data[:M_0], (0, 0), 0)

    # unrolled loop for different weightings
    for i in xrange(0, M_0, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, M_0)
        yield S_0, M_0

    for i in xrange(M_0, M, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, i+1)
        yield S_0, i+1

    for i in xrange(M, data.size, step):
        S_0 = moving_meanvar(data[i:i+step], S_0, M)
        yield S_0, M


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
                 help="duration of sliding window (s) for calculating mean and SD (default=%(default).1f)",
                 default=defaults.get('window', 2),
                 type=float,
                 metavar='SEC')
        addopt_f("--exclude-rms",
                 help="if set, exclude intervals where RMS > %(metavar)s%% above baseline",
                 type=float,
                 metavar='F')
        addopt_f("--exclude-duration",
                 help="only exclude intervals longer than %(metavar)s ms (default=%(default).0f)",
                 default=defaults.get('exclude_duration', 100),
                 metavar='MS')
        addopt_f("--exclude-baseline",
                 help="duration of interval (s) used to set RMS baseline (default=%(default).1f)",
                 default=defaults.get('exclude_baseline', 10),
                 metavar='SEC')

    def __init__(self, **options):
        util.set_option_attributes(self, options, window=2.0, step=100.,
                                   exclude_rms=None, exclude_duration=100., exclude_baseline=10.)
        self.last_sample_t = 0    # time of last sample
        self.stats = None         # statistics from sliding window
        self.nsamples = 0         # number of samples for which we have data
        self.queue = []           # queue for chunks while initializing smoother

    def send(self, chunk):

        # pass non-time series data
        if not "samples" in chunk.tags:
            Node.send(self, chunk)

        # convert time windows to sample counts
        n_window = int(self.window * chunk.dt)

        #gap = util.to_samples(chunk.offset - self.last_sample_t, chunk.dt)

        # update stats
        mean, var = self.stats = moving_meanvar(nx.asarray(chunk.data), self.nsamples, self.stats)
        self.nsamples = max(n_window, self.nsamples + chunk.data.size)
        self.last_sample_t = util.to_seconds(chunk.data.size, chunk.dt, chunk.offset)

        # if uninitialized, append to queue
        if self.nsamples < n_window:
            self.queue.append(chunk)
            return

        # flush the queue
        elif len(self.queue):
            for past_chunk in self.queue:
                scaled = (past_chunk.data - mean) / nx.sqrt(var)
                Node.send(self, past_chunk._replace(data=scaled))
            self.queue = []

        # process the current chunk
        scaled = (chunk.data - mean) / nx.sqrt(var)
        Node.send(self, chunk._replace(data=scaled))



# Variables:
# End:
