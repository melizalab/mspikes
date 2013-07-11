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

def test_rand_samples():
    from mspikes.modules.random_sources import rand_samples

    src = rand_samples()
    is_sampled = filters._has_tag('samples')

    class test_module(types.Node):
        """Wrapper class for testing the output of a module"""

        def __init__(self):
            self.count = 0

        def send(self, data):
            assert_true(is_sampled(data))
            assert_equal(data.data.size, src.chunk_size)
            assert_equal(data.offset, self.count)
            self.count += data.data.size

    tgt = test_module()
    src.add_target(tgt)

    for x in src:
        pass


def test_time_series_offset():
    from mspikes.modules import util

    f = util.time_series_offsets

    assert_equal(f(0, 1, 20, None, 100), (20, 100))
    assert_equal(f(20, 1, 20, 80, 100), (0, 60))

    assert_equal(f(0, 10, 20, 80, 1000), (200, 800))

    with assert_raises(TypeError):
        f(0, None, 20, 80, 5)


def test_splitter():
    from numpy import random, concatenate, array_equal
    from mspikes.modules import util

    data = types.DataBlock(id='random', offset=0, dt=1, data=random.randn(10000), tags=types.tag_set("samples"))

    splitter = util.splitter()

    x = []
    with util.chain_modules(splitter, util.visitor(lambda chunk: x.append(chunk.data))) as chain:
        chain.send(data)

    assert_true(array_equal(concatenate(x), data.data))




# Variables:
# End:
