# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""spike detection and extraction

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Fri Jul 12 14:05:16 2013
"""

import logging
import operator
import numpy as nx

from mspikes import util
from mspikes.modules import dispatcher
from mspikes.types import Node, tag_set

_log = logging.getLogger(__name__)


@dispatcher.parallel('id', "samples")
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
                 type=float,
                 required=True,
                 metavar='FLOAT')
        addopt_f("--interval",
                 help="the interval around the peak to extract (default=%(default)s)",
                 type=float,
                 default=(1.0, 2.0),
                 nargs=2,
                 metavar='MS')

    def __init__(self, **options):
        util.set_option_attributes(self, options, thresh=None, interval=(1.0, 2.0))
        self.reset()

    def reset(self):
        self.detector = None
        self.spike_queue = []
        self.last_chunk = None  # store last chunk in case spike splits across boundary

    def send(self, chunk):
        from mspikes.util import repeatedly
        from itertools import chain

        n_before, n_after = (util.to_samples(x / 1000., chunk.ds) for x in self.interval)

        # reset the detector if there's a gap or ds changes
        if self.last_chunk is not None:
            last_sample_t = util.to_seconds(self.last_chunk.data.size, self.last_chunk.ds, self.last_chunk.offset)
            gap = util.to_samples(chunk.offset - last_sample_t, chunk.ds)
            if gap > 1 or self.last_chunk.ds != chunk.ds:
                self.reset()
        if self.detector is None:
            self.detector = detect_spikes(self.thresh, util.to_samples(self.interval[1], chunk.ds))

        spike_it = chain(repeatedly(self.spike_queue.pop, 0),
                         ((t - n_before, t + n_after) for t in self.detector.send(chunk.data)))
        dt = nx.dtype([('start', nx.int32), ('spike', chunk.data.dtype, n_before + n_after)])
        spikes = nx.fromiter(self.get_spikes(chunk, spike_it), dt)

        if len(spikes):
            Node.send(self, chunk._replace(id=chunk.id + "_spikes",
                                           data=nx.fromiter(spikes, dtype=dt),
                                           tags=tag_set("events")))

        self.last_chunk = chunk

    def get_spikes(self, chunk, times):
        data = chunk.data

        for start, stop in times:
            if stop > data.size:
                # queue the spike until the next data chunk arrives
                self.spike_queue.append((start - data.size, stop - data.size))
                continue
            if start < 0 and self.last_chunk is not None:
                spk = nx.concatenate((self.last_chunk.data[slice(start, None)], data[slice(0, stop)]))
            else:
                spk = data[start:stop]

            yield (start, spk)


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
