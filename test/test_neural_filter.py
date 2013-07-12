# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest

import numpy as nx
from mspikes import types
from mspikes.modules import neural_filter, util

def test_exponential_filter():

    data = nx.asarray([100, 50, 150,])

    m_exp = [ 100.    ,   87.5  ,   103.125]
    v_exp = [ 1250., 1289.0625, 1516.11328125]
    g = neural_filter.smoother(neural_filter.moving_meanvar, 3)
    g.send(data)                # initialize
    for d, me, ve in zip(data, m_exp, v_exp):
        m, v = g.send(d)
        assert_equal(m, me)
        assert_equal(v, ve)

    # with step size 2
    m_exp = [(100 * 3 + 100 + 50.) / 5, (90 * 3 + 150.) / 4]
    v_exp = [(data.var() * 3 + (50-90)**2 + (100-90)**2) / 5, 1511.25]
    g = neural_filter.smoother(neural_filter.moving_meanvar, 3)
    g.send(data)                # initialize
    for i in xrange(0, 2):
        j = i * 2
        m, v = g.send(data[j:j + 2])
        assert_equal(m, m_exp[i])
        assert_equal(v, v_exp[i])

    # # with one data point from the past
    m_exp = [ (100. + 100. + 50) / 3, (100. + 100 + 50 + 150) / 4]
    g = neural_filter.smoother(neural_filter.moving_meanvar, 3, (100., 1000.), 1)
    assert_is_none(g.send(data[:1]))
    for d, me in zip(data[1:], m_exp):
        m, v = g.send([d])
        assert_equal(m, me)


def test_zscale():

    _randg = nx.random.RandomState(1)
    window_size = 4096
    chunk_size = 2048
    zscaler = neural_filter.zscale(window=window_size)

    out = []
    chunks = []
    data = _randg.randn(chunk_size * 100) * 5
    with util.chain_modules(zscaler, util.visitor(out.append)) as chain:
        for chunk in util.array_reader(data, 1, chunk_size):
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
        for chunk in util.array_reader(data, ds, chunk_size):
            chain.send(chunk)

    return data, out
    excl = filter(lambda x: "exclusions" in x.tags, out)
    assert_equal(len(excl), 1)
    assert_equal(excl[0].offset, t_window * 1.5)
    assert_equal(excl[0].data.size, 1)
    assert_equal(excl[0].data[0]['stop'], max(int(t_mindur * ds / 1000), chunk_size))




