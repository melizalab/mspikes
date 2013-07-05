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

    m,v = neural_filter.exponential_smoother(data, 3)
    assert_true(nx.array_equal(m, [ 100.    ,   87.5  ,   103.125]))
    assert_true(nx.array_equal(v, [ 1250., 1289.0625, 1516.11328125]))

    # with one data point from the past
    m,v = neural_filter.exponential_smoother(data, 3, 1, (100., 1000.))
    assert_true(nx.array_equal(m, [ 100.  ,   75.  ,   93.75]))
    assert_true(nx.array_equal(v, [  500.      ,   562.5     ,  1212.890625]))
