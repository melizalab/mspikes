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
from collections import namedtuple

from mspikes import util
from mspikes.types import Node, DataBlock, tag_set
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


@coroutine
def smoother(func, M, S0=None, N0=0):
    """A coroutine for applying a moving smoother to data arrays

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
    from numpy import concatenate, asarray

    init_queue = [()]
    N = N0
    try:
        while N < M:
            # return None while initializing
            X = asarray((yield))
            init_queue.append(X)
            N += X.size
        # calculate initial state from full length of the window
        X = concatenate(init_queue)
        S = func(X, N0, S0)
        while True:
            # note: send() assigns value to X, then loops and returns S
            X = asarray((yield S))
            S = func(X, M, S)
    except GeneratorExit:
        return


class _smoother(Node):
    """Modify a time series based on statistics in a sliding window

    This is a base class. Deriving classes should implement statefun() and
    datafun()

    """
    window = 2.0                # duration of sliding window, in seconds

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--window",
                 help="duration of sliding window (s) (default=%(default).1f)",
                 default=defaults.get('window', cls.window),
                 type=float,
                 metavar='SEC')

    def __init__(self, **options):
        util.set_option_attributes(self, options, window=self.window)
        self.last_sample_t = 0    # time of last sample
        self.state = None         # statistics from sliding window
        self.nsamples = 0         # number of samples for which we have data
        self.init_queue = []      # queue for chunks while initializing smoother

    def statefun(self, chunk, nsamples, state):
        """Return updated value for state incorporating new data"""
        raise NotImplementedError

    def datafun(self, chunk):
        """Process the data in chunk, updating self.state as needed

        """
        raise NotImplementedError

    def send(self, chunk):
        from mspikes.util import repeatedly

        # pass non-time series data
        if not "samples" in chunk.tags:
            Node.send(self, chunk)
            return

        # convert time windows to sample counts
        n_window = int(self.window * chunk.ds)

        # penalize for gaps - but still keep some old data
        if self.nsamples > n_window / 5:
            gap = util.to_samples(chunk.offset - self.last_sample_t, chunk.ds)
            self.nsamples = max(n_window / 5, self.nsamples - gap)

        # ensure that data is realized (e.g. from hdf5 arrays)
        chunk = chunk._replace(data=chunk.data[...])

        self.last_sample_t = util.to_seconds(chunk.data.size, chunk.ds, chunk.offset)

        # if uninitialized, append to init_queue
        if self.nsamples < n_window:
            self.init_queue.append(chunk)
            self.state = self.statefun(chunk, self.nsamples, self.state)
            self.nsamples = min(n_window, self.nsamples + chunk.data.size)
        else:
            # flush the init_queue
            for past_chunk in repeatedly(self.init_queue.pop, 0):
                self.datafun(past_chunk)
            # process the current chunk
            self.datafun(chunk)


class zscale(_smoother):
    """Center and rescale time series with a sliding window.

    Data are z-scaled by subtracting the mean and dividing by the standard
    deviation. The mean and SD of the data are calculated using a moving
    exponential smoother.

    """
    stat_type = namedtuple('chunk_stats', ('mean', 'var'))


    @classmethod
    def options(cls, addopt_f, **defaults):
        super(zscale, cls).options(addopt_f, **defaults)

    def __init__(self, **options):
        super(zscale, self).__init__(**options)

    def statefun(self, chunk, nsamples, state):
        return moving_meanvar(chunk.data, nsamples, state)

    def datafun(self, chunk):
        mean, var = self.state = self.statefun(chunk, self.nsamples, self.state)
        Node.send(self, chunk._replace(data=self.stat_type(mean, var), tags=tag_set("debug","scalar")))
        Node.send(self, chunk._replace(data=(chunk.data - mean) / nx.sqrt(var)))


class rms_exclude(zscale):
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
    window = 60.
    stat_type = namedtuple('chunk_stats', ('base_rms','rms_ratio',))

    @classmethod
    def options(cls, addopt_f, **defaults):
        super(rms_exclude, cls).options(addopt_f, **defaults)
        addopt_f("--max-rms",
                 help="if set, exclude intervals where relative RMS > %(metavar)s (default=%(default).1f)",
                 type=float,
                 default=defaults.get('max_rms', 1.15),
                 metavar='F')
        addopt_f("--min-duration",
                 help="only exclude intervals longer than %(metavar)s ms (default=%(default).0f)",
                 type=float,
                 default=defaults.get('exclude_duration', 200),
                 metavar='MS')

    def __init__(self, **options):
        super(rms_exclude, self).__init__(**options)
        util.set_option_attributes(self, options, max_rms=1.15, min_duration=200.)
        self.excl_queue = []     # need a separate queue to determine if the rms
                                # stayed above threshold for > min_duration

    def datafun(self, chunk):
        """Drop chunks that exceed the threshold"""
        from mspikes.util import to_samples

        mean, var = self.statefun(chunk, self.nsamples, self.state)
        rms_ratio = nx.sqrt(nx.var(chunk.data) / var)
        Node.send(self, chunk._replace(data=self.stat_type(var, rms_ratio), tags=tag_set("debug","scalar")))

        if rms_ratio > self.max_rms:
            self.excl_queue.append(chunk)
            return

        if len(self.excl_queue):
            first = self.excl_queue[0]
            duration = chunk.offset - first.offset
            if (duration > self.min_duration / 1000):
                # too much bad data - drop
                rec = ((to_samples(0, first.ds), to_samples(duration, first.ds), 'rms'),)
                excl = DataBlock(chunk.id, first.offset, first.ds,
                                 nx.rec.fromrecords(rec, names=('start', 'stop', 'reason')),
                                 tag_set("events", "exclusions"))
                Node.send(self, excl)
                print excl
            else:
                # release chunks
                for c in self.excl_queue:
                    Node.send(self, c)
            self.excl_queue = []

        Node.send(self, chunk)
        self.state = (mean, var)


# Variables:
# End:








