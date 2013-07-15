# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""spike detection and extraction

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Fri Jul 12 14:05:16 2013
"""

import logging
import numpy as nx

from mspikes import util
from mspikes.types import Node, DataBlock, tag_set

_log = logging.getLogger(__name__)

class spike_extract(Node):
    """Detect spike times in time series and extract waveforms

    accepts: _samples (time series of extracellular voltage)
    emits:   _events (marked point process, time + waveform)
    passes:  all other tags

    """

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--thresh",
                 help="detection threshold (negative values imply negative-going crossings)",
                 type=float,)
        addopt_f("--interval",
                 help="the interval around the peak to extract (in ms; default=%(default)s)",
                 type=float,
                 default=(1.0, 2.0),
                 nargs=2,)
        addopt_f("--resamp",
                 help="resampling factor to use in finding peaks (default=%(default)d)",
                 type=int,
                 default=3)

    def __init__(self, **options):
        util.set_option_attributes(self, options, thresh=None, interval=(1.0, 2.0), resamp=3)
        self.last_sample_t = 0
        self.last_ds = 0

    def send(self, chunk):
        # pass non-time series data
        if not "samples" in chunk.tags:
            Node.send(self, chunk)
            return

        # reset the detector if there's a gap or ds changes
        gap = util.to_samples(chunk.offset - self.last_sample_t, chunk.ds)
        if gap > 1 or self.last_ds != chunk.ds:
            self.detector = None

        n_before, n_after = (util.to_samples(x / 1000., chunk.ds) for x in self.interval)

        if self.detector is None:
            self.detector = detect_spikes(self.thresh, util.to_samples(self.interval[1], chunk.ds))

        dt = nx.dtype([('start', nx.int32), ('spike', chunk.data.dtype, n_before + n_after)])
        spikes = ((t - n_before, chunk.data[slice(t - n_before, t + n_after)])
                   for t in self.detector.send(chunk.data))

        Node.send(self, chunk._replace(data=nx.fromiter(spikes, dtype=dt), tags=tag_set("events")))

        self.last_sample_t = util.to_seconds(chunk.data.size, chunk.ds, chunk.offset)
        self.last_ds = chunk.ds


class detect_spikes(object):
    """ state machine implementation - 955 ms"""

    BelowThreshold = 1
    BeforePeak = 2
    AfterPeak = 3

    def __init__(self, thresh, n_after):
        """Construct spike detector.

        thresh -- the crossing threshold that triggers the detector. Positive
                  values imply positive-going crossings, and negative values
                  imply negative-going crossings

        n_after -- the maximum number of samples after threshold crossing to
                   look for the peak. If a peak has not been located within this
                   window, the crossing is considered an artifact and is not counted.

        """
        assert thresh != 0
        self.thresh = thresh
        self.n_after = n_after
        self.state = self.BelowThreshold

    def send(self, samples):
        """Detect spikes in a time series.

        Returns a list of indices corresponding to the peaks (or troughs) in the
        data. Retains state between calls. The detector should be reset if there
        is a gap in the signal.

        """
        from numpy import sign
        out = []
        tdir = sign(self.thresh)     # threshold crossing direction

        for i, x in enumerate(samples):
            if self.state is self.BelowThreshold:
                if sign(x - self.thresh) == tdir:
                    self.prev_val = x
                    self.n_after_crossing = 0
                    self.state = self.BeforePeak
            elif self.state is self.BeforePeak:
                if sign(self.prev_val - x) == tdir:
                    out.append(i - 1)
                    self.state = self.AfterPeak
                elif self.n_after_crossing > self.n_after:
                    self.state = self.BelowThreshold
                else:
                    self.prev_val = x
                    self.n_after_crossing += 1
            elif self.state is self.AfterPeak:
                if sign(self.thresh - x) == tdir:
                    self.state = self.BelowThreshold
        return out



# Variables:
# End:
