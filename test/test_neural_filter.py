# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest

import numpy as nx

from mspikes.modules import neural_filter


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
