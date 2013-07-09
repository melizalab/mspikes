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


# Variables:
# End:
