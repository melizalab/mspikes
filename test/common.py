# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""common test functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest

def assert_array_equal(a1, a2):
    from numpy import array_equal
    assert_true(array_equal(a1, a2), "Arrays differ: %s != %s" % (a1, a2))


def assert_arrays_equal(as1, as2):
    for a1, a2 in zip(as1, as2):
        assert_array_equal(a1, a2)
