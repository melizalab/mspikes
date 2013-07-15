# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""

from nose.tools import *
from nose.plugins.skip import SkipTest

import numpy as nx
import h5py

from mspikes.modules import spike_extraction, util

# a nice surrogate spike with 20 samples before peak and 40 after
a_spike = nx.array([-1290,  -483,  -136,  -148,  -186,   637,   328,    41,    63,
                    42,   377,   872,   639,   -17,   538,   631,   530,   693,
                    743,  3456,  6345,  5868,  4543,  3087,  1691,   830,   241,
                    -350,  -567,  -996,  -877, -1771, -1659, -1968, -2013, -2290,
                    -2143, -1715, -1526, -1108,  -500,   333,    25,  -388,  -368,
                    -435,  -817,  -858,  -793, -1089,   -16,  -430,  -529,  -252,
                    -3,  -786,   -47,  -266,  -963,  -365], dtype=nx.int16)
t_peak = a_spike.argmax()
t_trough = a_spike.argmin()



def test_detect_spikes():
    a_recording = nx.zeros(10000, dtype=nx.int16)
    times = [100, 400, 1200]
    for t in times:
        a_recording[t:t + a_spike.size] += a_spike

    detector = spike_extraction.detect_spikes(2000, 40)
    assert_sequence_equal(detector.send(a_recording), [t + t_peak for t in times])
    assert_sequence_equal(detector.send(-a_recording), [t + t_trough for t in times])

    detector = spike_extraction.detect_spikes(-4000, 40)
    assert_sequence_equal(detector.send(a_recording), [])
    assert_sequence_equal(detector.send(-a_recording), [t + t_peak for t in times])


def test_spike_extractor():
    from mspikes.util import to_samples
    # test splitting across chunks

    chunk_size = 1000
    out = []
    a_recording = nx.zeros(5000, dtype=nx.int16)

    times = [100,                     # normal spike
             chunk_size - t_peak - 5, # peak before boundary
             chunk_size * 2 - t_peak, # peak after boundary
             ]
    for t in times:
        a_recording[t:t + a_spike.size] += a_spike

    extractor = spike_extraction.spike_extract(thresh=4000, interval=(1.0, 2.0))

    with util.chain_modules(extractor, util.visitor(out.append)) as chain:
        for chunk in util.array_reader(a_recording, 20000, chunk_size):
            chain.send(chunk)

    starts = [to_samples(chunk.offset, chunk.ds) + chunk.data['start'] for chunk in out]
    assert_true(nx.array_equal(nx.concatenate(starts), times))

    assert_true(all(nx.array_equal(chunk.data['spike'][0], a_spike) for chunk in out))










