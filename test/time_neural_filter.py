# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""timing and profiling for neural filter

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jul 25 15:47:21 2013
"""

import numpy as nx
import cProfile
from mspikes.modules import neural_filter, util

N = 5000000
chunk_size = 10000

a_spike = nx.array([-1290,  -483,  -136,  -148,  -186,   637,   328,    41,    63,
                    42,   377,   872,   639,   -17,   538,   631,   530,   693,
                    743,  3456,  6345,  5868,  4543,  3087,  1691,   830,   241,
                    -350,  -567,  -996,  -877, -1771, -1659, -1968, -2013, -2290,
                    -2143, -1715, -1526, -1108,  -500,   333,    25,  -388,  -368,
                    -435,  -817,  -858,  -793, -1089,   -16,  -430,  -529,  -252,
                    -3,  -786,   -47,  -266,  -963,  -365], dtype=nx.int16)
a_recording = nx.zeros(N, dtype=nx.int16)
times = nx.arange(1000, N - 1000, 1000)
for t in times:
    a_recording[t:t + a_spike.size] += a_spike

scaler = neural_filter.zscale()

def time_run(source, target, *args, **kwargs):
    if isinstance(source, nx.ndarray):
        source = util.timeseries_reader(source, *args, **kwargs)
    for chunk in source:
        target.send(chunk)

cProfile.run('time_run(a_recording, scaler, 20000, 10000)','neural_filter.prof')

# Variables:
# End:

