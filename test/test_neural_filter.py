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

    data = nx.asarray([100., 50., 150.,])

    m_exp = [ 100.    ,   87.5  ,   103.125]
    v_exp = [ 1250., 1289.0625, 1516.11328125]
    for i,(m,v) in enumerate(neural_filter.exponential_smoother(data, 3, 1)):
        assert_equal(m, m_exp[i])
        assert_equal(v, v_exp[i])

    # with one data point from the past
    m_exp = [ 100.  ,   (100 + 100 + 50.) / 3  , (100 + 100 + 50 + 150) / 4 ]
    v_exp = [  500.      ,   (500 * 2 + (m_exp[1] - data[1])**2) / 3     ,  1152.7777777777778]
    for i,(m,v) in enumerate(neural_filter.exponential_smoother(data, 3, 1, 1, (100., 1000.))):
        assert_equal(m, m_exp[i])
        assert_equal(v, v_exp[i])

    # with step size 2
    m_exp = [(100 * 3 + 100 + 50.) / 5, (90 * 3 + 150.) / 4]
    v_exp = [(data.var() * 3 + (50-90)**2 + (100-90)**2) / 5, 1511.25]
    for i,(m,v) in enumerate(neural_filter.exponential_smoother(data, 3, 2)):
        assert_equal(m, m_exp[i])
        assert_equal(v, v_exp[i])
