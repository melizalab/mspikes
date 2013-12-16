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
                          [(22, x[:2]), (50, x[2:4]), (70, x[4:6]), (100, x[6:])])

    assert_sequence_equal([y for y in util.cutarray(x, cuts[:-1])],
                          [(22, x[:2]), (50, x[2:4]), (70, x[4:6]), (None, x[6:])],
                          "values larger than final cut point not placed in final bin")

    assert_sequence_equal([y for y in util.cutarray(x, [])],
                          [(None, x)],
                          "values for empty cut array not placed in single bin")

    assert_sequence_equal([y for y in util.cutarray(x, [0, 50])],
                          [(50, x[:4]), (None, x[4:])],
                          "values generated for empty bin")

    assert_sequence_equal([y for y in util.cutarray(x, [52, 54, 100])],
                          [(52, x[:5]), (100, x[5:])],
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
