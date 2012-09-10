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

def compare_times(data, times):
    thresh = 0.122
    if data.dtype.kind == 'i':
        thresh *= 2**(8 * data.dtype.itemsize - 1)
    tt = spikes.spike_times(data, thresh, 40)
    assert tt.shape==data.shape, "%s: time array shape unequal to data shape" % data.dtype
    assert all(tt==times), "%s: times unequal" % data.dtype

def test01_times():
    data = nx.load(test_file)
    times = data['times']
    for k,d in data.items():
        if k == 'times': continue
        yield compare_times, d, times

# Variables:
# End:
