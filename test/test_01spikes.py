# -*- coding: utf-8 -*-
# -*- mode: python -*-

import os
from nose.tools import *

import numpy as nx
from mspikes import spikes

# the test file is a compressed numpy file that should contain any number of different
# representations of a spike waveform, along with an array indicating the spike
# times. This is useful for ensuring that the code is agnostic to data type
test_dir = "data"
test_file = os.path.join(test_dir,"ex_spikes.npz")
test_times = 'times'

def compare_times(data, times):
    thresh = 0.122
    if data.dtype.kind == 'i':
        thresh *= 2**(8 * data.dtype.itemsize - 1)
    tt = spikes.spike_times(data, thresh, 40)
    assert tt.shape==data.shape, "%s: time array shape unequal to data shape" % data.dtype
    assert all(tt==times), "%s: times unequal" % data.dtype

def compare_stats(data):
    smean,sstd = spikes.signal_stats(data)
    assert_almost_equal(smean,data.mean(),5,"%s: means not equal (%f, %f)" % (data.dtype, smean, data.mean()))
    assert_almost_equal(sstd,data.std(),5,"%s: stdev not equal (%f, %f)" % (data.dtype, sstd, data.std()))

def test01_times():
    data = nx.load(test_file)
    times = data[test_times]
    for k,d in data.items():
        if k == test_times: continue
        yield compare_times, d, times

def test03_stats():
    data = nx.load(test_file)
    for k,d in data.items():
        if k == test_times: continue
        yield compare_stats, d


# Variables:
# End:
