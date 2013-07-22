# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test arf_io

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from test.common import *

import itertools
import numpy as nx
import arf
from fractions import Fraction

from mspikes.types import DataBlock
from mspikes.modules import arf_io, util


class Entry:
    def __init__(self, jack_usec, jack_frame):
        self.attrs = dict(jack_usec=jack_usec, jack_frame=jack_frame)
        self.name = "dummy"

class ScratchFile(object):
    def __init__(self):
        self.idx = 0

    def __call__(self, name, *args, **kwargs):
        self.idx += 1
        return arf.open_file("%s_%d" % (name, self.idx), *args, **kwargs)

get_scratch_file = ScratchFile()

a_spike = nx.array([-1290,  -483,  -136,  -148,  -186,   637,   328,    41,    63,
                    42,   377,   872,   639,   -17,   538,   631,   530,   693,
                    743,  3456,  6345,  5868,  4543,  3087,  1691,   830,   241,
                    -350,  -567,  -996,  -877, -1771, -1659, -1968, -2013, -2290,
                    -2143, -1715, -1526, -1108,  -500,   333,    25,  -388,  -368,
                    -435,  -817,  -858,  -793, -1089,   -16,  -430,  -529,  -252,
                    -3,  -786,   -47,  -266,  -963,  -365], dtype=nx.int16)

def random_spikes(n, maxt, ds=None):
    """ generate a record array with marked point process structure """
    dt = nx.dtype([('start', nx.int32), ('spike', nx.int16, 60)])
    if ds is None:
        t = nx.random.uniform(0, maxt, n)
    else:
        t = nx.random.randint(0, maxt * ds, n)
    return nx.rec.fromarrays([t, nx.tile(a_spike, (n,1))], dtype=dt)


def test_corrected_jack_frame():

    idx = nx.arange(100, dtype=nx.uint32)
    frames = idx * 1000
    usecs = (frames * 50).astype(nx.uint64)

    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames))
    func = arf_io.corrected_jack_frame()
    times = map(func, entries)
    assert_array_equal(sorted(frames), times)

    # overflow the frame counter
    entries = (Entry(u, f) for u, f in itertools.izip(usecs, frames - 50000))
    func = arf_io.corrected_jack_frame()
    times = map(func, entries)
    assert_array_equal(sorted(frames), times)


def test_entry_iteration():
    # create an in-memory hdf5 file
    fp = get_scratch_file("tmp", driver="core", backing_store=False)

    srate = 50000
    dset_times = (0., 100., 200.)
    expected_times = []

    # real timebase
    e = arf.create_entry(fp, "entry-real", 0., sample_count=0)
    expected_times.append(0.)    # from structure block
    for j, t in enumerate(dset_times):
        d = arf.create_dataset(e, "dset_%d" % j, (0,), offset=t, units="s", sampling_rate=None)
        expected_times.append(t)

    # sampled timebase
    e = arf.create_entry(fp, "entry-sampled", 1000., sample_count=1000 * srate)
    expected_times.append(1000.)    # from structure block
    for j, t in enumerate(dset_times):
        d = arf.create_dataset(e, "dset_%d" % j, (0,), offset=int(t * srate), sampling_rate=srate)
        expected_times.append(t + 1000)

    r = arf_io.arf_reader(fp)
    dset_times = [d.offset for d in r]
    assert_sequence_equal(dset_times, expected_times)

    # make the file look like something from arfxplog - now it will use the
    # sampling rate for the dataset offset
    fp.attrs['program'] = 'arfxplog'
    fp.attrs['sampling_rate'] = srate

    r = arf_io.arf_reader(fp)
    dset_times = [d.offset for d in r]
    assert_sequence_equal(dset_times, [Fraction(t) for t in expected_times])


def compare_entries(name, src, tgt):
    assert_true(name in tgt)
    src, tgt = (fp[name] for fp in (src, tgt))
    src_attrs, tgt_attrs = (dict(entry.attrs) for entry in (src, tgt))
    assert_array_equal(src_attrs.pop('timestamp'), tgt_attrs.pop('timestamp'))
    assert_dict_equal(src_attrs, tgt_attrs)
    for dset in src:
        compare_datasets(dset, src, tgt)


def compare_datasets(name, src, tgt):
    assert_true(name in tgt)
    d1, d2 = (entry[name] for entry in (src, tgt))
    assert_equal(d1.attrs.get('sampling_rate', None), d2.attrs.get('sampling_rate', None))
    assert_equal(d1.attrs.get('offset', 0), d2.attrs.get('offset', 0))
    if d1.dtype.names is None:
        assert_array_equal(d1, d2)
    else:
        # can't directly compare structured arrays
        assert_sequence_equal(d1.dtype.names, d2.dtype.names)
        for name in d1.dtype.names:
            assert_array_equal(d1[name], d2[name])


def mirror_file(sampled):
    src = get_scratch_file("src", driver="core", backing_store=False)
    tgt = get_scratch_file("tgt", driver="core", backing_store=False)
    srate = 1000

    # populate the source file
    for i in range(5):
        t = i * 2.
        e = arf.create_entry(src, "entry_%02d" % i, timestamp=t, sample_count=int(t * srate), an_attribute="a_value")
        arf.create_dataset(e, "spikes", random_spikes(100, 2.0), units=('s','mV'))
        for j in range(3):
            arf.create_dataset(e, "pcm_%02d" % j, nx.random.randn(1000), units="mV", sampling_rate=srate)
    if sampled:
        arf.set_attributes(src, program='arfxplog', sampling_rate=srate)

    reader = arf_io.arf_reader(src)
    writer = arf_io.arf_writer(tgt)
    splitter = util.splitter(nsamples=100)

    with util.chain_modules(splitter, writer) as chain:
        # send structure chunks first to make sure writer can slot data in later
        queue = []
        for chunk in reader:
            if "structure" in chunk.tags:
                chain.send(chunk)
            else:
                queue.append(chunk)
        for chunk in queue:
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


def test_file_mirroring():
    for sampled in (False, True):
        yield mirror_file, sampled


def test_arf_writer_pproc():
    """test writing point process data

    Point process times need to be adjusted relative to the offset of the
    dataset where they're stored. If some or all events in a chunk could be
    stored in a later entry, they must be.

    """
    srate = 1000
    tgt = get_scratch_file("tgt", driver="core", backing_store=False)
    spikes = random_spikes(1000, 4.0, srate)

    for i in range(2):
        t = i * 2.
        arf.create_entry(tgt, "entry_%d" % i, timestamp=t, sample_count=int(t * srate))

    writer = arf_io.arf_writer(tgt)
    writer.send(DataBlock("spikes", 1.0, srate, spikes, ("events",)))

    d1 = tgt['entry_0']['spikes']
    d2 = tgt['entry_1']['spikes']
    assert_equal(d1.size + d2.size, spikes.size)
    assert_equal(d1.size, sum(spikes['start'] < 2.0))


def test_arf_writer_gap():
    """test whether data with gaps and other irregularities are stored correctly

    If there's a gap in time series data, the writer should create another
    entry, store the data in a dataset with the same name, and set the timestamp
    of the entry so that the data have the correct temporal spacing.

    """
    src = get_scratch_file("src", driver="core", backing_store=False)
    tgt = get_scratch_file("tgt", driver="core", backing_store=False)

    N = 1000
    gap = 2.0
    e = arf.create_entry(src, "entry", timestamp=0, sample_count=0)
    arf.create_dataset(e, "pcm", nx.random.randn(N), units="mV", sampling_rate=N)

    reader = arf_io.arf_reader(src)
    writer = arf_io.arf_writer(tgt)

    blocks = range(0, 1000, 1000/4)
    for chunk in reader:
        # split data into three parts
        if "samples" in chunk.tags:
            writer.send(chunk._replace(data=chunk.data[blocks[0]:blocks[1]]))
            writer.send(chunk._replace(offset=gap, data=chunk.data[blocks[1]:blocks[2]]))
            writer.send(chunk._replace(offset=gap + 0.25, data=chunk.data[blocks[2]:blocks[3]]))
            writer.send(chunk._replace(offset=gap * 2, data=chunk.data[blocks[3]:]))
        else:
            writer.send(chunk)

    assert_equal(len(tgt), 3)
    entries = sorted(tgt.itervalues(), key=arf.entry_time)
    assert_sequence_equal([arf.entry_time(entry) for entry in entries], [gap * i for i in range(3)])
    nsamples = 0
    for entry in entries:
        assert_true('pcm' in entry)
        assert_equal(entry['pcm'].attrs.get('offset', 0), 0)
        nsamples += entry['pcm'].size
    assert_equal(nsamples, N)


def test_writeback():
    """test writing data back to source file"""
    src = get_scratch_file("src", driver="core", backing_store=False)
    N = 1000

    e = arf.create_entry(src, "entry", timestamp=0, sample_count=0)
    arf.create_dataset(e, "pcm", nx.random.randn(N), units="mV", sampling_rate=N,
                       maxshape=(None,))
    # a non-extensible entry
    arf.create_dataset(e, "pcmx", nx.random.randn(N), units="mV", sampling_rate=N)
    arf.create_dataset(e, "spikes", random_spikes(100, 1.0), units=('s','mV'),
                       maxshape=(None,))

    reader = arf_io.arf_reader(src)
    writer = arf_io.arf_writer(src)

    for chunk in reader:
        if chunk.id == "pcmx":
            with assert_raises(arf_io.ArfError):
                # non-extensible entry
                writer.send(chunk._replace(offset=1))
        elif chunk.id == "pcm":
            with assert_raises(arf_io.ArfError):
                # still overlaps
                writer.send(chunk._replace(offset=0.5))
            # okay
            writer.send(chunk._replace(offset=2))
        elif chunk.id == "spikes":
            with assert_raises(arf_io.ArfError):
                writer.send(chunk)
            # as long as they're not at exactly the same offset they're merged
            # have to read the data in order to avoid extending the dataset
            # we're trying to write
            writer.send(chunk._replace(offset=0.1, data=chunk.data[:]))
        else:
            writer.send(chunk)


def test_adjust_event_times():

    eq = nx.array_equal
    f = arf_io.adjust_event_times
    times = nx.arange(0, 20000, 1000, dtype=nx.int32)

    for t in (nx.float, nx.uint32, nx.int64):
        assert_true(eq(f(times, t(0), t(0)), times))
        assert_true(eq(f(times, t(100), t(0)), times + 100))
        assert_true(eq(f(times, t(100), t(1000)), times - 900))


def test_split_point_process():
    t = nx.arange(100,200,10)

    assert_arrays_equal(arf_io.split_point_process(t, None), (t, []))
    assert_arrays_equal(arf_io.split_point_process(t, 0), ([], t))
    assert_arrays_equal(arf_io.split_point_process(t, 150), (t[t<150], t[t>=150]))


# Variables:
# End:
