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
import arf

from mspikes.modules import arf_io

class Entry:

    def __init__(self, jack_usec, jack_frame):
        self.attrs = dict(jack_usec=jack_usec, jack_frame=jack_frame)

def test_attritemgetter():

    obj = Entry(0,10)

    assert_equal(arf_io.attritemgetter('jack_usec')(obj), 0)
    with assert_raises(KeyError):
        arf_io.attritemgetter('name2')(obj)


def test_keyiter_attr():

    # if attribute is mising, skip it
    entries = (Entry(0,10), Entry(10,20))
    entries[0].name = 'first'   # logger will look for this field when skipping
    entries[1].attrs['sample_count'] = 10

    assert_sequence_equal(tuple(arf_io.keyiter_attr(entries, 'sample_count')),
                          ((arf_io.attritemgetter('sample_count')(entries[1]), entries[1]),))


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


def test_entry_iteration():
    # this is pretty messy and overly fragile

    # create an in-memory hdf5 file
    fp = h5py.File("tmp", driver="core", backing_store=False)

    srate = 50000
    dset_times = (0., 100., 200.)
    expected_times = []

    f = arf.file(fp)

    # real timebase
    e = f.create_entry("entry-real", 0, sample_count=0)
    for j, t in enumerate(dset_times):
        d = e.add_data("dset_%d" % j, (), offset=t, units="s", sampling_rate=None)
        expected_times.append(t)

    # sampled timebase
    e = f.create_entry("entry-sampled", 1000, sample_count=1000 * srate)
    for j, t in enumerate(dset_times):
        d = e.add_data("dset_%d" % j, (), offset=int(t * srate), sampling_rate=srate)
        expected_times.append(t + 1000)


    r = arf_io.arf_reader(fp)
    dset_times = [d.offset for d in r.iterdatasets()]
    assert_sequence_equal(dset_times, expected_times)

    # make the file look like something from arfxplog - now it will use the
    # sampling rate for the dataset offset
    fp.attrs['program'] = 'arfxplog'
    fp.attrs['sampling_rate'] = srate

    # add some incompatible datasets - should be skipped
    e.add_data("dset_bad", (), offset=0, sampling_rate=srate/3)

    r = arf_io.arf_reader(fp)
    assert_equal(r.sampling_rate, srate)

    dset_times = [d.offset for d in r.iterdatasets()]
    assert_sequence_equal(dset_times, [int(t * srate) for t in expected_times])


def test_dset_timebase():

    def f(msg, expected, *args):
        assert_equal(arf_io.dset_offset(*args), expected, msg)

    f("real entry timebase, real dset", 110., 100., None, 10., None)
    f("real entry, sampled dset", 110., 100., None, 100, 10)
    f("sampled entry, real dset", 1100, 1000, 10, 10., None)
    f("sampled entry, sampled dset (same rate)", 1100, 1000, 10, 100, 10)
    f("sampled entry, sampled dset (convertable rates)", 1100, 1000, 10, 1000, 100)

    # sampled entry, sampled dset (inconvertible rates)
    with assert_raises(ValueError):
        arf_io.dset_offset(1000, 10, 1000, 66)


# Variables:
# End:
