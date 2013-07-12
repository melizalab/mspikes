# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""spike detection and extraction

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Fri Jul 12 14:05:16 2013
"""

import logging
import numpy as nx
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
                 help="detection threshold (can be negative)",
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
        pass

    def send(self, chunk):
        pass


def extract_spikes(samples, thresh, before, after):
    """slow pure python implementation"""
    from numpy import argmax, argmin

    i = 0
    peakfun = argmax if thresh > 0 else argmin
    while i < samples.size:
        x = samples[i]
        if x - thresh > 0:
            peak_ind = peakfun(samples[i:i + after]) + i
            idx = slice(peak_ind - before, peak_ind + after)
            yield (peak_ind, samples[idx])
            i = peak_ind + 1
            # search for first sample below threshold
            while i < samples.size and (samples[i] - thresh) > 0:
                i += 1
        else:
            i += 1



# Variables:
# End:
