# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test mspikes.util

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from test.common import *
from mspikes import util

def test_cutarray():
    x = range(10, 100, 10)
    cuts = [22, 50, 70, 100]

    assert_sequence_equal([y for y in util.cutarray(x, cuts)],
                          [(-1, x[:2]), (0, x[2:4]), (1, x[4:6]), (2, x[6:])])

    assert_sequence_equal([y for y in util.cutarray(x, [])],
                          [(-1, x)],
                          "values for empty cut array not placed in single bin")

    assert_sequence_equal([y for y in util.cutarray(x, [0, 50])],
                          [(0, x[:4]), (1, x[4:])],
                          "values generated for leftmost bin")

    assert_sequence_equal([y for y in util.cutarray(x, [52, 54, 100])],
                          [(-1, x[:5]), (1, x[5:])],
                          "values generated for empty bin in middle of sequence")


def test_repeatedly():
    arr = [1, 2, 3]
    assert_sequence_equal([x for x in util.repeatedly(arr.pop, 0)],
                          [1, 2, 3])
    assert_equal(arr, [])


def test_pairiter():
    seq = [1, 2, 3, 4, 5]
    assert_sequence_equal([x for x in util.pair_iter(seq)],
                          [(1, 2), (2, 3), (3, 4), (4, 5)])

# Variables:
# End:
