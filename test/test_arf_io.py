# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest
import inspect
import itertools
import h5py

from mspikes.modules import arf_io

class Entry:

    def __init__(self, jack_usec, jack_frame):
        self.attrs = dict(jack_usec=jack_usec, jack_frame=jack_frame)

def test_attritemgetter():

    obj = Entry(0,10)

    assert_equal(arf_io.attritemgetter('jack_usec')(obj), 0)
    with assert_raises(KeyError):
        arf_io.attritemgetter('name2')(obj)


def test_keyiter_jack_frame():
    import numpy as nx

    # dummy list of times, shuffled to test sorting
    idx = nx.arange(100, dtype=nx.uint32)
    nx.random.shuffle(idx)
    frames = idx * 1000
    usecs = (frames * 50).astype(nx.uint64)


    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames))
    keys = [k for k, e in arf_io.keyiter_jack_frame(entries)]
    assert_true(nx.array_equal(sorted(frames), keys))


    # overflow the frame counter
    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames - 50000))
    keys = [k for k, e in arf_io.keyiter_jack_frame(entries)]
    assert_true(nx.array_equal(sorted(frames), keys))


def test_data_sampling_rate():

    # create an in-memory hdf5 file
    srate = 50000
    f = h5py.File("tmp", driver="core", backing_store=False)
    for i in range(20):
        e = f.create_group("entry_%d" % i)
        for j in range(5):
            d = e.create_dataset("dset_%d" % j, shape=(10,))
            d.attrs['sampling_rate'] = srate

    assert_equal(arf_io.data_sampling_rate(f, strict=True), srate)

    e = f.create_group("bad")
    d = e.create_dataset("bad", shape=(10,))
    d.attrs['sampling_rate'] = srate / 2

    with assert_raises(ValueError):
        arf_io.data_sampling_rate(f, strict=True)


# Variables:
# End:
