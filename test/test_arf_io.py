# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from nose.tools import *
from nose.plugins.skip import SkipTest

import itertools
import numpy as nx
import arf
from fractions import Fraction

from mspikes.modules import arf_io, util


class Entry:
    def __init__(self, jack_usec, jack_frame):
        self.attrs = dict(jack_usec=jack_usec, jack_frame=jack_frame)
        self.name = "dummy"


def random_spikes(n):
    """ generate a record array with marked point process structure """
    dt = nx.dtype([('start', nx.int32), ('spike', nx.int16, 60)])
    return nx.empty(n, dtype=dt)


def test_attritemgetter():

    obj = Entry(0,10)
    assert_equal(arf_io.attritemgetter('jack_usec')(obj), 0)
    assert_is_none(arf_io.attritemgetter('name2')(obj))


def test_corrected_jack_frame():

    idx = nx.arange(100, dtype=nx.uint32)
    frames = idx * 1000
    usecs = (frames * 50).astype(nx.uint64)

    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames))
    func = arf_io.corrected_jack_frame()
    times = map(func, entries)
    assert_true(nx.array_equal(sorted(frames), times))

    # overflow the frame counter
    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames - 50000))
    func = arf_io.corrected_jack_frame()
    times = map(func, entries)
    assert_true(nx.array_equal(sorted(frames), times))


def test_entry_iteration():
    # create an in-memory hdf5 file
    fp = arf.open_file("tmp", driver="core", backing_store=False)

    srate = 50000
    dset_times = (0., 100., 200.)
    expected_times = []

    # real timebase
    e = arf.create_entry(fp, "entry-real", 0., sample_count=0)
    expected_times.append(0.)    # from structure block
    for j, t in enumerate(dset_times):
        d = arf.create_dataset(e, "dset_%d" % j, (), offset=t, units="s", sampling_rate=None)
        expected_times.append(t)

    # sampled timebase
    e = arf.create_entry(fp, "entry-sampled", 1000., sample_count=1000 * srate)
    expected_times.append(1000.)    # from structure block
    for j, t in enumerate(dset_times):
        d = arf.create_dataset(e, "dset_%d" % j, (), offset=int(t * srate), sampling_rate=srate)
        expected_times.append(t + 1000)

    r = arf_io.arf_reader(fp)
    dset_times = [d.offset for d in r]
    assert_sequence_equal(dset_times, expected_times)

    # make the file look like something from arfxplog - now it will use the
    # sampling rate for the dataset offset
    fp.attrs['program'] = 'arfxplog'
    fp.attrs['sampling_rate'] = srate

    # add some incompatible datasets - should be skipped
    d = arf.create_dataset(e, "dset_bad", (), offset=10, sampling_rate=srate/3)

    r = arf_io.arf_reader(fp)
    assert_equal(r.sampling_rate, srate)

    dset_times = [d.offset for d in r]
    assert_sequence_equal(dset_times, [Fraction(t) for t in expected_times])


def compare_entries(name, src, tgt):
    assert_true(name in tgt)
    src, tgt = (fp[name] for fp in (src, tgt))
    src_attrs, tgt_attrs = (dict(entry.attrs) for entry in (src, tgt))
    assert_true(nx.array_equal(src_attrs.pop('timestamp'), tgt_attrs.pop('timestamp')))
    assert_dict_equal(src_attrs, tgt_attrs)
    for dset in src:
        compare_datasets(dset, src, tgt)


def compare_datasets(name, src, tgt):
    assert_true(name in tgt)
    d1, d2 = (entry[name] for entry in (src, tgt))
    assert_equal(d1.attrs.get('sampling_rate', None), d2.attrs.get('sampling_rate', None))
    assert_equal(d1.attrs.get('offset', 0), d2.attrs.get('offset', 0))
    if d1.dtype.names is None:
        assert_true(nx.array_equal(d1, d2))
    else:
        assert_sequence_equal(d1.dtype.names, d2.dtype.names)
        for name in d1.dtype.names:
            assert_true(nx.array_equal(d1[name], d2[name]))


def test_file_mirroring():
    src = arf.open_file("src", driver="core", backing_store=False)
    tgt = arf.open_file("tgt", driver="core", backing_store=False)

    # populate the source file
    for i in range(10):
        e = arf.create_entry(src, "entry_%02d" % i, timestamp=i * 10., sample_count=i * 1000, an_attribute="a_value")
        arf.create_dataset(e, "spikes", random_spikes(100), units=('s','mV'))
        for j in range(3):
            arf.create_dataset(e, "pcm_%02d" % j, nx.random.randn(1000), units="mV", sampling_rate=1000)

    reader = arf_io.arf_reader(src)
    writer = arf_io.arf_writer(tgt)
    splitter = util.splitter(nsamples=100)

    with util.chain_modules(splitter, writer) as chain:
        for chunk in reader:
            chain.send(chunk)

    for entry in src:
        compare_entries(entry, src, tgt)
        assert_sequence_equal(src[entry].keys(), tgt[entry].keys())

    # now copy data to tgt again to test writing to an existing file
    for chunk in reader:
        if "structure" not in chunk.tags:
            chunk = chunk._replace(id=chunk.id + "_new")
        writer.send(chunk)

    for entry in src:
        compare_entries(entry, src, tgt)
    src.close()
    tgt.close()


def test_arf_writer_gap():
    src = arf.open_file("src", driver="core", backing_store=False)
    tgt = arf.open_file("tgt", driver="core", backing_store=False)

    N = 1000
    e = arf.create_entry(src, "entry", timestamp=0, sample_count=0)
    arf.create_dataset(e, "pcm", nx.random.randn(N), units="mV", sampling_rate=N)

    reader = arf_io.arf_reader(src)
    writer = arf_io.arf_writer(tgt)

    for chunk in reader:
        # split data and introduce a chunk
        if "samples" in chunk.tags:
            writer.send(chunk._replace(data=chunk.data[:N/2]))
            writer.send(chunk._replace(offset=2., data=chunk.data[N/2:]))
        else:
            writer.send(chunk)

    src.close()
    tgt.close()


def test_dset_timebase():

    def f(msg, expected, *args):
        assert_equal(arf_io.data_offset(*args), expected, msg)

    f("real entry timebase", 100., 100., None)
    f("sampled entry", Fraction(1000,10), 1000, 10)
    f("real entry timebase, real dset", 110., 100., None, 10., None)
    f("real entry, sampled dset", 110., 100., None, 100, 10)
    f("sampled entry, real dset", Fraction(1100,10), 1000, 10, 10., None)
    f("sampled entry, sampled dset (same rate)", Fraction(1100, 10), 1000, 10, 100, 10)
    f("sampled entry, sampled dset (convertable rates)", Fraction(1100, 10), 1000, 10, 1000, 100)

    # sampled entry, sampled dset (inconvertible rates)
    with assert_raises(ValueError):
        arf_io.data_offset(1000, 10, 1000, 66)


# Variables:
# End:
