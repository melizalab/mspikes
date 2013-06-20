# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Test module input and output

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 20 14:59:30 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest

from mspikes import types
from mspikes import filters

class test_module(types.Sink):
    """Wrapper class for testing the output of a module"""

    def __init__(self, testf):
        self.testf = testf

    def recv(self, data):
        return self.testf(data)


def test_rand_samples():
    from mspikes.modules.random_sources import rand_samples

    src = rand_samples()

    count = 0
    def f(data):
        assert_true(filters.sampled(data))
        assert_equal(data.data.size, src.chunk_size)
        assert_equal(data.offset, count)
        return count + data.data.size

    tgt = test_module(f)
    src.add_sink(tgt)

    for x in src:
        count = x[0]


# Variables:
# End:
