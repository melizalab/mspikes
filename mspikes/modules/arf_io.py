# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions and classes for reading and writing ARF files.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import h5py
import numpy
import logging
import functools
import operator
from fractions import Fraction
from mspikes import util
from mspikes.types import DataBlock, Node, RandomAccessSource, tag_set

_log = logging.getLogger(__name__)

class arf_reader(RandomAccessSource):
    """Source data from an ARF/HDF5 file

    Produces data by iterating through entries of the file in temporal order,
    emitting chunks separately for each dataset in the entries. By default the
    timestamp of the entries is used to calculate offsets for the chunks, but
    for ARF files created by 'arfxplog' and 'jrecord' the sample clock can be
    used as well.

    emits: data blocks from ARF file (_events and _samples)
           entry start times (_structure)

    Note: using sample-based offsets with files that were recorded at different
    sampling rates or with different instances of the data collection program
    will lead to undefined behavior because the sample counts will not be
    consistent within the file.

    """
    _log = logging.getLogger(__name__ + ".arf_reader")

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
        addopt_f("--ignore-xruns",
                 help="use entries with xruns or other errors (default is to skip)",
                 action='store_true')
        addopt_f("--skip-sort",
                 help="skip initial sort of entries",
                 action='store_true')


    def __init__(self, filename, **options):
        import re
        util.set_option_attributes(self, options,
                                   start=0, stop=None, use_timestamp=False, use_xruns=False)

        if isinstance(filename, h5py.File):
            self.file = filename
        else:
            self.file = h5py.File(filename, "r")
        self._log.info("input file: %s", self.file.filename)

        channels = options.get("channels", None)
        if channels:
            try:
                rx = (re.compile(p).search for p in channels)
                self.chanp = util.chain_predicates(*rx)
            except re.error, e:
                raise ValueError("bad channel regex: %s" % e.message)
        else:
            self.chanp = true_p

        entries = options.get("entries", None)
        if entries:
            try:
                rx = (re.compile(p).search for p in entries)
                self.entryp = util.chain_predicates(*rx)
            except re.error, e:
                raise ValueError("bad entries regex: %s" % e.message)
        else:
            self.entryp = true_p

        self.entries = self._entry_table()
        self.sampling_rate = self._sampling_rate()
        if self.sampling_rate:
            self._log.info("file sampling rate (nominal): %d Hz", self.sampling_rate)

    @property
    def creator(self):
        """The program that created the file, or None if unknown"""
        if self.file.attrs.get('program', None) == 'arfxplog':
            return 'arfxplog'
        elif "jill_log" in self.file:  # maybe check for jack_sample attribute?
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
                self._log.info("couldn't determine ARF file source, using default sort method")
        elif self.creator == 'arfxplog':
            keyname = "sample_count"
            keyiter = functools.partial(keyiter_attr, name=keyname)
        elif self.creator == 'jill':
            keyname = "jack_frame"
            keyiter = keyiter_jack_frame
        self._log.info("sorting entries by '%s'", keyname)

        # filter by name and type
        entries = (entry for name, entry in self.file.iteritems()
                   if self.entryp(name) and isinstance(entry, h5py.Group))
        # keyiter extracts key, entry pairs; then we sort by key
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

    def __iter__(self):
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
                self._log.warn("'%s' was marked with an error: '%s'%s", entry.name, entry.attrs['jill_error'],
                          " (skipping)" if not self.use_xruns else "")
                if not self.use_xruns:
                    continue

            entry_time = util.to_seconds(entry_time - time_0, self.sampling_rate)

            if self.start and entry_time < self.start:
                continue
            if self.stop and entry_time > self.stop:
                continue

            # emit structure blocks to indicate entry onsets
            chunk = DataBlock(id=entry.name,
                              offset=entry_time,
                              ds=self.sampling_rate,
                              data=(),
                              tags=tag_set("structure"))
            Node.send(self, chunk)
            yield chunk

            for id, dset in entry.iteritems():
                if not self.chanp(id):
                    continue

                dset_ds = dset.attrs.get('sampling_rate', None)

                dset_time = util.to_seconds(dset.attrs.get('offset', 0), dset_ds, entry_time)
                if isinstance(dset_time, Fraction) and (dset_time * self.sampling_rate).denominator != 1:
                    self._log.warn("'%s' sampling rate (%s) incompatible with file sampling rate (%d)",
                              dset.name, dset_ds, self.sampling_rate)
                    continue

                if "units" in dset.attrs and dset.attrs["units"] in ("s", "samples","ms"):
                    tag = "events"
                else:
                    tag = "samples"

                chunk = DataBlock(id=id, offset=dset_time, ds=dset_ds, data=dset, tags=tag_set(tag))
                Node.send(self, chunk)
                yield chunk


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


def keyiter_jack_frame(entries, do_sort=True):
    """Iterate entries producing (key, entry), with key = jack_frame

    jack_frame values are converted from uint32 values (which may overflow) to
    uint64 values

    """
    from operator import itemgetter
    from numpy import uint64, seterr
    orig = seterr(over='ignore')   # ignore overflow warning

    # first sort by jack_usec, a uint64
    usec = keyiter_attr(entries, "jack_usec")
    if do_sort:
        usec = iter(sorted(usec, key=itemgetter(0)))

    # then convert the jack_frame uint32's to uint64's by incrementing. this may
    # not be very efficient, and won't work if there's a gap longer than the
    # size of the frame counter; could potentially do some kind of arithmetic
    # with the usec variable and the sample rate.
    _, entry = usec.next()
    last = entry.attrs['jack_frame']
    frame = uint64(0)
    yield (frame, entry)
    for _, entry in usec:
        current = entry.attrs['jack_frame']
        frame += current - last
        last = current
        yield (frame, entry)

    seterr(**orig)              # restore numpy error settings


def corrected_sampling_rate(keyed_entries):
    """Calculate the sampling rate relative to the system clock"""
    from arf import timestamp_to_float
    kf = attritemgetter('timestamp')
    entries = (keyed_entries[0], keyed_entries[-1])
    (s1, t1), (s2, t2) = ((s,timestamp_to_float(kf(e))) for s, e in entries)
    return (s2 - s1) / (t2 - t1)


def data_offset(entry_time, entry_ds, dset_time=0, dset_ds=None):
    """Return offset of a dataset in seconds, as either a float or a Fraction"""
    dsype = type(entry_time)

    if dset_ds is not None:
        dset_time = Fraction(int(dset_time), int(dset_ds))

    if entry_ds is None:
        # converts to float
        return entry_time + dset_time
    else:
        entry_time = Fraction(long(entry_time), long(entry_ds))
        if dset_ds is None:
            # find nearest sample
            return entry_time + Fraction(int(round(dset_time * entry_ds)), int(entry_ds))
        else:
            val = entry_time + dset_time
            if (val * entry_ds).denominator != 1:
                raise ValueError("dataset timebase is incompatible with entry timebase")
            return val


# Variables:
# End:
