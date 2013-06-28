# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""A Source that reads data from an ARF file.

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

    # then convert the jack_frame  uint32's to uint64's by incrementing. this
    # may not be very efficient; could potentially do some kind of arithmetic
    # with the usec variable and sample_rate (validating sample rate in the process)
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


def data_sampling_rate(file, strict=False):
    """check that all datasets have same sampling rate and log the ones that don't"""
    _log.info("validating datasets")
    sr = [None]
    def sampling_rate_visitor(name, obj):
        if isinstance(obj, h5py.Dataset):
            rate = obj.attrs.get("sampling_rate", None)
            if rate is None:
                pass
            elif sr[0] is None:
                sr[0] = rate
            elif sr[0] != rate:
                msg = "'%s' sampling rate %d doesn't match rate for file (%d)" % (name, rate, sr[0])
                if strict:
                    raise ValueError(msg)
                else:
                    _log.warn(msg)

    file.visititems(sampling_rate_visitor)
    return sr[0]


class arf_reader(RandomAccessSource):
    """Read data from an ARF/HDF5 file"""

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="names or regexps of channels (default all)",
                 metavar='CH',
                 nargs='+')
        addopt_f("--times",
                 help="range of times (in s) to analyze (default all)",
                 type=float,
                 metavar='FLOAT',
                 nargs=2)
        addopt_f("--entries",
                 help="names or regexps of entries (default all)",
                 metavar='P',
                 nargs="+")
        addopt_f("--use-timestamp",
                 help="use entry timestamp for timebase and ignore other fields",
                 action='store_true')

    def __init__(self, filename, **options):
        import re
        self.file = h5py.File(filename, "r")
        self.times = options.get("times", None)
        self.use_timestamp = options.get("use_timestamp", False)

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
        entries = (entry for name, entry in self.file.iteritems() if self.entryp(name))
        return sorted(keyiter(entries), key=operator.itemgetter(0))

    def _sampling_rate(self):
        """Infer sampling rate from file"""
        if self.use_timestamp or self.creator is None:
            return None
        elif self.creator == 'arfxplog':
            return self.file.attrs['sampling_rate']
        elif self.creator == 'jill':
            # assumes entries have been validated
            return data_sampling_rate(self.file)

    def __iter__(self):
        # questions about how to iterate:
        #
        # 1. does it matter what order we go through entries? Yes for some
        # applications but not for others. Sorting takes time though because we
        # have to load all the entries and inspect the timestamp attributes (or
        # some other key.
        #
        # 2. validate whether the requested channels are homogeneous across
        # entries? probably not, it's rather pathological if they're not
        #
        # 3. How about whether there's overlapping data?  Okay with the arf
        # spec, but do we try: to straighten it out?  How to detect?  Need to
        # keep track of whether the time has passed the start time of the next entry
        #
        # 4. dealing with different timebases and formats. Some arf files will
        # have sample counts, which should probably be used instead of
        # timestamps when possible.  However, these have to be converted to real
        # times at some point.  And, actually, there's no canonical conversion
        # factor because datasets don't have to be at the same sampling rate.


        pass

# Variables:
# End:
