# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions and classes for reading and writing ARF files.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import h5py
import logging
import functools
import operator
from mspikes import util
from mspikes.types import DataBlock, RandomAccessSource

_log = logging.getLogger(__name__)


def true_p(*args):
    return True


def attritemgetter(name):
    """Return a function that extracts arg.attr['name']"""
    return lambda arg: arg.attrs[name]


def keyiter_attr(entries, name, fun=None):
    """Iterate entries producing (key, entry) pairs.

    key is entry.attrs['name'], or if fun is defined, fun(entry.attrs['name'])

    Skips entries with no 'name' attribute

    """
    keyfun = attritemgetter(name)
    if fun is not None:
        keyfun = util.compose(fun, keyfun)
    for entry in entries:
        try:
            yield keyfun(entry), entry
        except KeyError:
            _log.info("'%s' skipped (missing '%s' attribute)", entry.name, name)


def keyiter_jack_frame(entries):
    """Iterate entries producing (key, entry), with key = jack_frame

    jack_frame values are converted from uint32 values (which may overflow) to
    uint64 values

    """
    from operator import itemgetter
    from numpy import uint64, seterr
    orig = seterr(over='ignore')   # ignore overflow warning

    # first sort by jack_usec, a uint64
    usec_sorted = sorted(keyiter_attr(entries, "jack_usec"), key=itemgetter(0))

    # then convert the jack_frame uint32's to uint64's by incrementing. this may
    # not be very efficient, and won't work if there's a gap longer than the
    # size of the frame counter; could potentially do some kind of arithmetic
    # with the usec variable and the sample rate.
    _, entry = usec_sorted[0]
    last = entry.attrs['jack_frame']
    frame = uint64(0)
    yield (frame, entry)
    for _, entry in usec_sorted[1:]:
        current = entry.attrs['jack_frame']
        frame += current - last
        last = current
        yield (frame, entry)

    seterr(**orig)


def dset_offset(entry_time, entry_dt, dset_offset, dset_dt):
    """calculate the total offset of a dataset, converting to entry timebase as needed"""
    import fractions

    dtype = type(entry_time)

    if entry_dt == dset_dt:
        val = entry_time + dset_offset
    elif entry_dt is None:
        val = entry_time + dtype(dset_offset) / dset_dt
    elif dset_dt is None:
        val = entry_time + dtype(dset_offset * entry_dt)
    elif fractions.Fraction(*sorted((entry_dt, dset_dt))).numerator == 1:
        val = entry_time + dtype(dset_offset * entry_dt / dset_dt)
    else:
        raise ValueError("dataset timebase is incompatible with entry timebase")

    return dtype(val)


def set_option_attributes(obj, opts, **attrs):
    """For each key, value in **attrs, set obj.key = opts.get(key, value)"""
    for key, value in attrs.iteritems():
        setattr(obj, key, opts.get(key, value))


class arf_reader(RandomAccessSource):
    """Source data from an ARF/HDF5 file

    Produces data by iterating through entries of the file in temporal order,
    emitting chunks separately for each dataset in the entries. By default the
    timestamp of the entries is used to calculate offsets for the chunks, but
    for ARF files created by 'arfxplog' and 'jrecord' the sample clock can be
    used as well.

    Using sample-based offsets with files that were recorded at different
    sampling rates or with different instances of the data collection program
    will lead to undefined behavior because the sample counts will not be
    consistent within the file.

    """
    blockchunks = 64               # number of hdf5 chunks to process at once

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="names or regexps of channels to read (default all)",
                 metavar='CH',
                 nargs='+')
        addopt_f("--start",
                 help="time (in s) to start reading (default 0)",
                 type=float,
                 default=0,
                 metavar='FLOAT')
        addopt_f("--stop",
                 help="time (in s) to stop reading (default None)",
                 type=float,
                 metavar='FLOAT')
        addopt_f("--entries",
                 help="names or regexps of entries to read (default all)",
                 metavar='P',
                 nargs="+")
        addopt_f("--use-timestamp",
                 help="use entry timestamp for timebase and ignore other fields",
                 action='store_true')
        addopt_f("--use-xruns",
                 help="use entries with xruns or other errors (default is to skip)",
                 action='store_true')

    def __init__(self, filename, **options):
        import re
        set_option_attributes(self, options,
                              start=0, stop=None, use_timestamp=False, use_xruns=False)

        if isinstance(filename, h5py.File):
            self.file = filename
        else:
            self.file = h5py.File(filename, "r")

        if "channels" in options:
            rx = (re.compile(p).search for p in options['channels'])
            self.chanp = util.chain_predicates(*rx)
        else:
            self.chanp = true_p

        if "entries" in options:
            rx = (re.compile(p).search for p in options['entries'])
            self.entryp = util.chain_predicates(*rx)
        else:
            self.entryp = true_p

        self.entries = self._entry_table()
        self.sampling_rate = self._sampling_rate()
        _log.info("file sampling rate: %s", self.sampling_rate)

    @property
    def creator(self):
        """The program that created the file, or None if unknown"""
        if self.file.attrs.get('program', None) == 'arfxplog':
            return 'arfxplog'
        elif "jill_log" in self.file:
            return "jill"
        else:
            return None

    def _entry_table(self):
        """ Generate a table of entries and start times """
        from arf import timestamp_to_float

        if self.use_timestamp or self.creator is None:
            keyname = "timestamp"
            keyiter = functools.partial(keyiter_attr, name='timestamp', fun=timestamp_to_float)
            if self.creator is None:
                _log.info("couldn't determine ARF file source, using default sort method")
        elif self.creator == 'arfxplog':
            keyname = "sample_count"
            keyiter = functools.partial(keyiter_attr, name=keyname)
        elif self.creator == 'jill':
            keyname = "jack_frame"
            keyiter = keyiter_jack_frame
        _log.info("sorting entries by '%s'", keyname)

        # filter by name
        entries = (entry for name, entry in self.file.iteritems()
                   if self.entryp(name) and isinstance(entry, h5py.Group))
        return sorted(keyiter(entries), key=operator.itemgetter(0))

    def _sampling_rate(self):
        """Infer sampling rate from file"""
        if self.use_timestamp or self.creator is None:
            return None
        elif self.creator == 'arfxplog':
            return self.file.attrs['sampling_rate']
        elif self.creator == 'jill':
            # returns sampling rate of first dataset
            def srate_visitor(name, obj):
                if isinstance(obj, h5py.Dataset):
                    # if None is returned the iteration will continue
                    return obj.attrs.get("sampling_rate", None)
            return self.file.visititems(srate_visitor)

    def iterdatasets(self):
        """Iterate through the datasets.

        yields DataBlocks with the data field referencing the dataset object

        Datasets that don't match the entry and dataset selectors are skipped,
        as are datasets that have timebases inconsistent with the rest of the
        file.

        """
        time_0 = self.entries[0][0]
        for entry_time, entry in self.entries:
            # check for marked errors
            if "jill_error" in entry.attrs:
                _log.warn("'%s' was marked with an error: '%s'%s", entry.name, entry.attrs['jill_error'],
                          " (skipping)" if not self.use_xruns else "")
                if not self.use_xruns:
                    continue

            for id, dset in entry.iteritems():
                if not self.chanp(id):
                    continue

                dset_dt = dset.attrs.get('sampling_rate', None)
                try:
                    dset_time = dset_offset(entry_time - time_0, self.sampling_rate,
                                            dset.attrs.get('offset', 0), dset_dt)
                except ValueError:
                    _log.warn("'%s' sampling rate (%s) incompatible with file sampling rate (%d)",
                              dset.name, dset_dt, self.sampling_rate)
                    continue

                is_pointproc = "units" in dset.attrs and dset.attrs["units"] in ("s", "samples")

                yield DataBlock(id=id, repr=1 - is_pointproc, offset=dset_time, dt=dset_dt, data=dset)

    def __iter__(self):
        """Iterate through the data in the file"""
        from collections import defaultdict

        # monitor the time in each channel to check for inconsistencies
        dtype = type(self.entries[0][0])
        cp = self.channel_position = defaultdict(dtype)
        for dset in self.iterdatasets():
            # check for overlap (within channel)
            if dset.offset < cp[dset.id]:
                _log.warn("'%s' (start=%s) overlaps with previous dataset (end=%s)",
                          dset.data.name, dset.offset, cp[dset.id])
            # restrict by time
            nframes = dset.data.shape[0]
            blocksize = self.blockchunks * (dset.data.chunks[0] if dset.data.chunks else 1024)
            indices = xrange(max(0, (self.start - dset.offset / self.sampling_rate) * dset.dt),
                             min(nframes, (self.stop - dset.offset / self.sampling_rate) * dset.dt
                                 if self.stop else nframes),
                             blocksize)
            for i in indices:
                t = dset_offset(dset.offset, self.sampling_rate, i, dset.dt)
                data = dset.data[slice(i, i + blocksize), ...]
                yield dset._replace(offset=t, data=data)

            cp[dset.id] = dtype(dset.offset + nframes)
            # optionally check for consistency of timestamps and frame counts


# Variables:
# End:
