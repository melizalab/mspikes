# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
from __future__ import division
import logging
import numpy as nx
from collections import namedtuple

from mspikes import util
from mspikes.types import Node, DataBlock, tag_set
from mspikes.modules import dispatcher


class _smoother(Node):
    """Modify a time series based on statistics in a sliding window

    This is a base class. Deriving classes should implement statefun() and
    datafun()

    """
    def __init__(self, **options):
        util.set_option_attributes(self, options, window=2.0)
        self._log.info("window size: %.2f s", self.window)
        self.first_sample_t = None   # time of first sample in window
        self.last_sample_t = None    # time of last sample
        self.state = None         # statistics from sliding window
        self.weight = 0           # number of samples for which we have data
        self.init_queue = []      # queue for chunks while initializing smoother

    def statfun(self, chunk):
        """Return statistics for new data"""
        raise NotImplementedError

    def datafun(self, chunk):
        """Process the data in chunk, updating self.state as needed"""
        raise NotImplementedError

    def send(self, chunk):
        from mspikes.util import repeatedly
        # pass non-time series data
        if not "samples" in chunk.tags:
            Node.send(self, chunk)
            return

        # if data is not in memory, read it once now
        if not isinstance(chunk.data, nx.ndarray):
            chunk = chunk._replace(data=chunk.data[:])
        N = chunk.data.size

        # this implementation is a poor man's ringbuffer. A tail 'pointer'
        # indicates how many samples are averaged in self.state. Data are queued
        # until this number exceeds the minimum window size. If there are gaps,
        # the past sample count is penalized.
        if self.first_sample_t is None:
            self.first_sample_t = chunk.offset
        if self.last_sample_t is None:
            self.last_sample_t = chunk.offset
        # convert time windows to sample counts
        n_window = int(self.window * chunk.ds)
        nsamples = util.to_samples(chunk.offset - self.first_sample_t, chunk.ds)
        gap = util.to_samples(chunk.offset - self.last_sample_t, chunk.ds)

        # check for gap > window
        if gap > n_window:
            nsamples = 0
            self.first_sample_t = chunk.offset
        # if uninitialized, add to queue and update stats
        if nsamples < n_window:
            self.init_queue.append(chunk)
            stats = self.statfun(chunk)
            if self.weight:
                self.state = (self.state * self.weight + stats) / (self.weight + N)
            else:
                self.state = stats / N
        else:
            # flush the init_queue
            for past_chunk in repeatedly(self.init_queue.pop, 0):
                self.datafun(past_chunk)
            # process the current chunk. penalize for gaps.
            self.weight = max(0, max(self.weight, n_window) - gap)
            self.datafun(chunk)

        self.weight = min(n_window, self.weight + N)
        self.last_sample_t = util.to_seconds(N, chunk.ds, chunk.offset)

    def close(self):
        from mspikes.util import repeatedly
        # flush the queue
        for past_chunk in repeatedly(self.init_queue.pop, 0):
            self.datafun(past_chunk)
        Node.close(self)


@dispatcher.parallel('id', "samples")
class zscale(_smoother):
    """Center and rescale time series, optionally excluding noisy intervals

    modifies: _samples [(data - mean) / rms]
    emits:    _scalar (mean, rms, relative rms),
              _exclusions (intervals when relative rms > threshold)

    Exclusion: movement artifacts are characterized by large transient increases
    in signal power and intervals with strong artifacts should be excluded from
    spike detection or clustering. Exclusion is based on the power relative to
    the sliding window average, which allows a single criterion to be used for
    different channels and accounts for slow drifts in noise power over time.

    The exclusion algorithm is primarily designed for single channels. For
    multiple electrodes, it may be more effective to remove artifacts by
    subtracting a common average reference.

    """
    window = 60.
    stat_type = namedtuple('chunk_stats', ('mean','rms','rms_ratio',))
    _log = logging.getLogger("%s.zscale" % __name__)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--window",
                 help="duration of sliding window (s) (default=%(default).1f)",
                 default=defaults.get('window', cls.window),
                 type=float,
                 metavar='SEC')
        if not defaults.get("exclude", False):
            addopt_f("--exclude",
                     help="if set, drop intervals where relative RMS exceeds threshold",
                     action="store_true")
        addopt_f("--max-rms",
                 help="exclusion threshhold (default=%(default).2f)",
                 type=float,
                 default=defaults.get('max_rms', 1.15),
                 metavar='F')
        addopt_f("--min-duration",
                 help="only exclude intervals longer than %(metavar)s ms (default=%(default).0f)",
                 type=float,
                 default=defaults.get('exclude_duration', 200),
                 metavar='MS')

    def __init__(self, **options):
        _smoother.__init__(self, **options)
        util.set_option_attributes(self, options, exclude=True, max_rms=1.15, min_duration=200.)
        if self.exclude:
            self._log.info("excluding intervals with RMS %.3f times baseline", self.max_rms)
        self.excl_queue = []     # need a separate queue to determine if the rms
                                # stayed above threshold for > min_duration

    def statfun(self, chunk):
        from mspikes.stats import moments
        return moments(chunk.data)

    def datafun(self, chunk):
        """Drop chunks that exceed the threshold"""
        from mspikes.util import to_samples

        N = chunk.data.size
        stats = self.statfun(chunk)
        # current and previous variance
        variances = [s[1] - s[0] ** 2 for s in (self.state, stats / N)]
        rms_ratio = nx.sqrt(variances[1] / variances[0])
        # smoothed statistics
        smoothed = (self.state * self.weight + stats) / (self.weight + N)
        mean = smoothed[0]
        rms = nx.sqrt(smoothed[1])

        stat_chunk = chunk._replace(data=self.stat_type(mean, rms, rms_ratio), tags=tag_set("scalar"))

        # rescale data first, then decide if to queue it
        # should really rescale the threshold downstream, not the data
        chunk = chunk._replace(data=(chunk.data - mean) / rms)
        if self.exclude and rms_ratio > self.max_rms:
            self.excl_queue.extend((stat_chunk, chunk))
            return

        if self.excl_queue:
            first = self.excl_queue[0]
            duration = chunk.offset - first.offset
            if (duration > self.min_duration / 1000):
                # too much bad data - drop
                rec = ((to_samples(0, first.ds), to_samples(duration, first.ds), bytes(chunk.id), 'rms'),)
                excl = DataBlock('exclusions', first.offset, first.ds,
                                 nx.rec.fromrecords(rec, names=('start', 'stop', 'dataset', 'reason')),
                                 tag_set("events", "exclusions"))
                Node.send(self, excl)
                self._log.info("excluded data in '%s' from %.2f to %.2f s",
                               chunk.id, first.offset, chunk.offset)
            else:
                # release chunks
                for c in self.excl_queue:
                    Node.send(self, c)
            self.excl_queue = []

        Node.send(self, stat_chunk)
        Node.send(self, chunk)
        self.state = smoothed


# Variables:
# End:

