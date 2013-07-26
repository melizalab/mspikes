# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from test.common import *

import numpy as nx
from mspikes.modules import neural_filter, util

def test_zscale():
    _randg = nx.random.RandomState(1)
    window_size = 4096
    chunk_size = 2048
    zscaler = neural_filter.zscale(window=window_size, exclude=False)

    out = []
    chunks = []
    data = _randg.randn(chunk_size * 100) * 5
    with util.chain_modules(zscaler, util.visitor(out.append)) as chain:
        for chunk in util.timeseries_reader(data, 1, chunk_size):
            chain.send(chunk)
            chunks.append(chunk)

    for i,chunk in enumerate(out):
        if "scalar" in chunk.tags:
            mean, rms, rms_ratio = chunk.data
        elif "samples" in chunk.tags:
            data = chunks.pop(0)
            assert_true(nx.array_equal((data.data - mean) / rms, chunk.data))


def test_rms_exclude():
    _randg = nx.random.RandomState(1)
    nx.seterr(invalid='raise')  # make sure we flag problems

    chunk_size = 4096
    ds = 4096
    t_window = 60.
    t_mindur = 200.
    n_window = int(t_window * ds)

    excluder = neural_filter.zscale(exclude=True, window=t_window, min_duration=t_mindur)

    data = _randg.randn(n_window * 2)
    noise_idx = slice(n_window * 1.5, n_window * 1.5 + int(t_mindur * 3 * ds / 1000))
    data[noise_idx] *= 1.7

    out = []
    with util.chain_modules(excluder, util.visitor(out.append)) as chain:
        for chunk in util.timeseries_reader(data, ds, chunk_size, gap=100):
            chain.send(chunk)

    return data, out
    excl = filter(lambda x: "exclusions" in x.tags, out)
    assert_equal(len(excl), 1)
    assert_equal(excl[0].offset, t_window * 1.5)
    assert_equal(excl[0].data.size, 1)
    assert_equal(excl[0].data[0]['stop'], max(int(t_mindur * ds / 1000), chunk_size))




