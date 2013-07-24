# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""common test functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
import sys
from nose.tools import *
from nose.plugins.skip import SkipTest

def assert_array_equal(a1, a2):
    from numpy import array_equal
    assert_true(array_equal(a1, a2), "Arrays differ: %s != %s" % (a1, a2))


def assert_arrays_equal(as1, as2):
    for a1, a2 in zip(as1, as2):
        assert_array_equal(a1, a2)

# python 2.6 shims
if sys.hexversion < 0x02070000:
    def assert_sequence_equal(seq1, seq2, *args, **kwargs):
        assert_true(all(a == b for a, b in zip(seq1, seq2)), *args, **kwargs)

    def assert_is_none(obj, *args, **kwargs):
        assert_true(obj is None, *args, **kwargs)

    def assert_set_equal(set1, set2, *args, **kwargs):
        assert_equal(set(set1).symmetric_difference(set2), set(), *args, **kwargs)

    def assert_dict_equal(dict1, dict2, *args, **kwargs):
        assert_set_equal(dict1.keys(), dict2.keys(), *args, **kwargs)
        assert_true(all(dict2[k] == v for k, v in dict1.items()), *args, **kwargs)

    # import contextlib

    # @contextlib.contextmanager
    # def assert_raises(expected):
    #     import sys
    #     try:
    #         yield               # context
    #     except:
    #         pass
    #     finally:
    #         raise AssertionError("failed to raise expected exception %s" % expected)

    class AssertRaisesContext(object):
        def __init__(self, expected):
            self.expected = expected

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, tb):
            self.exception = exc_val
            assert_equal(exc_type, self.expected)
            # if you get to this line, the last assertion must have passed
            # suppress the propagation of this exception
            return True

    def assert_raises(expected):
        return AssertRaisesContext(expected)




