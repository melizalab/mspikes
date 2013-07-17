# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions and classes for reading and writing ARF files.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import logging
from fractions import Fraction

import h5py
import arf

from mspikes import util
from mspikes import filters
from mspikes.types import DataBlock, Node, RandomAccessSource, tag_set, MspikesError

_log = logging.getLogger(__name__)


class ArfError(MspikesError):
    """Raised for errors reading or writing ARF files"""
    pass


class _base_arf(object):
    """Base class for arf reader and writer"""

    @classmethod
    def _log(cls):
        return logging.getLogger("%s.%s" % (__name__, cls.__name__))

    def __init__(self, filename, mode='r'):
        if isinstance(filename, h5py.File):
            self.file = filename
        else:
            self.file = arf.open_file(filename, mode)

    @property
    def creator(self):
        """The program that created the file, or None if unknown"""
        if self.file.attrs.get('program', None) == 'arfxplog':
            return 'arfxplog'
        elif "jill_log" in self.file:  # maybe check for jack_sample attribute?
            return "jill"
        else:
            return None

    def get_offset_function(self, use_timestamp=False):
        """Return a function that extracts offsets from entries

        use_timestamp -- force use of timestamp attribute even if sample count
                         attributes are present

        """
        from arf import timestamp_to_float
        keyname = "timestamp"
        fun = util.compose(timestamp_to_float, attritemgetter(keyname))

        if self.creator is None:
            self._log().info("couldn't determine ARF file source, using default sort method")
        elif use_timestamp:
            pass
        elif self.creator == 'arfxplog':
            keyname = "sample_count"
            fun = attritemgetter(keyname)
        elif self.creator == 'jill':
            keyname = "jack_frame"
            fun = corrected_jack_frame()
        self._log().info("sorting entries by '%s'", keyname)
        return fun

    def _make_entry_table(self, keyfun, presorted=True):
        """Generate a table of entries and start times.

        sort -- sort the entries based on key. can be set to False if it's
                already known that the entries were created in order

        """
        from arf import keys_by_creation
        from operator import itemgetter
        from itertools import izip, imap

        try:
            # try to get entries sorted by creation time; this may fail if the
            # creation order wasn't tracked
            entries = [self.file[name] for name in keys_by_creation(self.file)
                       if self.entryp(name) and self.file.get(name, getclass=True) == h5py.Group]
        except RuntimeError:
            presorted = False
            entries = [self.file[name] for name in self.file
                       if self.entryp(name) and self.file.get(name, getclass=True) == h5py.Group]

        if not presorted and self.creator == 'jill':
            entries.sort(key=attritemgetter('jack_usec'))

        out = [(t,e) for t, e in izip(imap(keyfun, entries), entries) if t is not None]
        if not presorted:
            out.sort(key=itemgetter(0))
        return out

class arf_reader(_base_arf, RandomAccessSource):
    """Source data from an ARF/HDF5 file

    emits:  _events (point process datasets)
            _samples (time series datasets)
            _structure (entry start times)

    Iterates through _entries of the file in temporal order, emitting chunks
    separately for each dataset in the _entries. By default the timestamp of the
    _entries is used to calculate offsets for the chunks, but for ARF files
    created by 'arfxplog' and 'jrecord' the sample clock can be used as well.

    """
    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="names or regexps of channels to read (default all)",
                 metavar='CH',
                 nargs='+')
        addopt_f("--start",
                 help="exclude entries before this time (in s; default 0)",
                 type=float,
                 default=0,
                 metavar='FLOAT')
        addopt_f("--stop",
                 help="exclude entries after this time (in s; default None)",
                 type=float,
                 metavar='FLOAT')
        addopt_f("--entries",
                 help="names or regexps of entries to read (default all)",
                 metavar='P',
                 nargs="+")
        addopt_f("--use-timestamp", help=""" use entry timestamp for timebase and ignore other fields. May lead to
        warnings about data overlap because of jitter in the system clock. Using
        sample-based times from files recorded at multiple sampling rates or
        different clock start times may lead to undefined behavior""",
                 action='store_true')
        addopt_f("--ignore-xruns",
                 help="use entries with xruns or other errors (default is to skip)",
                 action='store_true')
        addopt_f("--skip-sort", help="""skip initial sort of entries. only use
        this if creation order was tracked and the entries are already in the correct order""",
                 action='store_true')


    def __init__(self, filename, **options):
        import re
        util.set_option_attributes(self, options,
                                   start=0, stop=None,
                                   use_timestamp=False,
                                   ignore_xruns=False,
                                   skip_sort=False)

        _base_arf.__init__(self, filename, "r")
        self._log().info("input file: %s", self.file.filename)

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

        self._entries = self._make_entry_table(self.get_offset_function(self.use_timestamp), self.skip_sort)
        self.sampling_rate = self._sampling_rate()
        if self.sampling_rate:
            self._log().info("file sampling rate (nominal): %d Hz", self.sampling_rate)

    def __iter__(self):
        """Iterate through the datasets.

        yields DataBlocks with the data field referencing the dataset object

        Datasets that don't match the entry and dataset selectors are skipped,
        as are datasets that have timebases inconsistent with the rest of the
        file.

        """
        time_0 = self._entries[0][0]
        for entry_time, entry in self._entries:
            # check for marked errors
            if "jill_error" in entry.attrs:
                self._log().warn("'%s' was marked with an error: '%s'%s", entry.name, entry.attrs['jill_error'],
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
                              data=entry.attrs,
                              tags=tag_set("structure"))
            Node.send(self, chunk)
            yield chunk

            for id, dset in entry.iteritems():
                if not self.chanp(id):
                    continue

                dset_ds = dset.attrs.get('sampling_rate', None)

                dset_time = util.to_seconds(dset.attrs.get('offset', 0), dset_ds, entry_time)
                if isinstance(dset_time, Fraction) and (dset_time * self.sampling_rate).denominator != 1:
                    self._log().warn("'%s' sampling rate (%s) incompatible with file sampling rate (%d)",
                              dset.name, dset_ds, self.sampling_rate)
                    continue

                tags = dset_tags(dset)

                chunk = DataBlock(id=id, offset=dset_time, ds=dset_ds, data=dset, tags=tags)
                Node.send(self, chunk)
                yield chunk

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


class arf_writer(_base_arf, Node):
    """Write chunks to an ARF/HDF5 file. """

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to write (created if it doesn't exist)")
        addopt_f("--compress",
                 help="the compression level to use (default=%(default)d)",
                 default=9,
                 choices=range(10),
                 type=int,
                 metavar='INT')
        addopt_f("--target-entry",
                 help=""" specify a target entry for data. If not supplied, tries to guess based on
                 structure of source file or timestamps in target file. An error
                 will be thrown if the data can't be placed""",
                 metavar='NAME',)

    def __init__(self, filename, **options):
        util.set_option_attributes(self, options, compress=9, default_entry=None)
        _base_arf.__init__(self, filename, "a")
        self._log().info("output file: %s", self.file.filename)
        self._entry = None
        self._offset_fun = self.get_offset_function()

    def send(self, chunk):
        if "structure" in chunk.tags and self.default_entry is None:
            self._set_entry(chunk)
        elif filters.any_tag("samples", "events")(chunk):
            entry = self._get_entry(chunk)
            self._write_data(entry, chunk)

    def _create_entry(self, name, offset, **attributes):
        """Create a new entry in the target file

        name -- the name of the entry
        offset -- the offset of the entry in the data stream

        Optional arguments:

        timestamp -- if supplied, the timestamp of the new entry in the arf file
                     is set to this. If not supplied, inferred from the
                     difference in seconds between offset and the previous
                     entry. If no previous entry, the current time is used.

        Additional keyword arguments are set as attributes of the new entry

        """
        import datetime
        try:
            timestamp = attributes.pop('timestamp')
        except KeyError:
            raise               # FIXME no timestamp
            if self._entry:
                # infer timestamp from previous entry
                timestamp = (arf.timestamp_to_float(self._entry.attrs['timestamp']) +
                             (offset - self._offset_fun(self._entry)))
            else:
                timestamp = datetime.datetime.now()
        self._entry = arf.create_entry(self.file, name, timestamp, **attributes)
        self._datasets = {}     # dict of datasets by id

    def _set_entry(self, chunk):
        """ Set the target entry based on a structure chunk """
        if chunk.id in self.file:
            self._entry = self.file[chunk.id]
            if not matches_entry(chunk, self._entry):
                raise ArfError("an _entry named '%s' exists in the target file,"
                               "but has the wrong timestamp or uuid", chunk.id)
                # TODO ask the user to decide
            self._datasets = {}
        else:
            self._create_entry(chunk.id, chunk.offset, **chunk.data)

    def _get_entry(self, chunk):
        """ Look up target entry for data chunk """
        from itertools import dropwhile
        if self._entry:
            return self._entry
        elif self.default_entry is not None:
            # create default target (here to delay until needed)
            self._create_entry(self.default_entry, type(chunk.offset)(0), creator='mspikes.arf_writer')
            return self._entry
        else:
            # fallback is to try to look up by time, finding the closest entry
            # with a time less than the offset. of course, we have to do this
            # for every chunk. TODO search a numpy array for speed
            if self._entry_table is None:
                self._entries = self._entry_table(sort=True)
            try:
                etime, entry = dropwhile(lambda x: x[0] < chunk.offset, self._entries).next()
                return entry
            except StopIteration:
                raise LookupError("unable to find a target entry with offset < %.2f" % float(chunk.offset))

    def _write_data(self, entry, chunk):
        """Look up target dataset for chunk in entry and write data.

        Creates new datasets as needed.

        """
        from mspikes.types import DataError
        # compute offset relative to entry
        offset = chunk.offset - arf.timestamp_to_float(entry.attrs['timestamp'])
        if chunk.ds is not None:
            offset = util.to_samples(offset, chunk.ds)
        try:
            dset = self._datasets[chunk.id]
            if dset.attrs.get('sampling_rate', None) != chunk.ds:
                raise DataError("sampling rate of '%s' (offset=%.3f) doesn't match target dataset '%s'" %
                                (chunk.id, float(chunk.offset), dset.name))
            if "samples" in chunk.tags:
                # verify alignment for sampled data
                if dset.size + dset.attrs.get('offset', 0) != offset:
                    raise NotImplementedError("need to create a new entry for gaps/overlaps")
            arf.append_data(dset, chunk.data)
        except KeyError:
            # set chunk size and max shape for new dataset
            if "samples" in chunk.tags:
                chunks = chunk.data.shape
                units = ''
            else:
                chunks = True   # auto-chunk size
                units = 's' if chunk.ds is None else 'samples'
                if chunk.data.dtype.names is not None:
                    # compound dtype requires units for each field
                    units = tuple((units if x == 'start' else '') for x in chunk.data.dtype.names)
            maxshape = (None,) + chunk.data.shape[1:]
            dset = arf.create_dataset(entry, chunk.id, chunk.data, units=units,
                                      chunks=chunks, maxshape=maxshape, compression=self.compress,
                                      sampling_rate=chunk.ds, offset=offset)
            self._datasets[chunk.id] = dset


def true_p(*args):
    return True


def attritemgetter(name):
    """Return a function that extracts arg.attr['name']"""
    def fun(arg):
        try:
            return arg.attrs[name]
        except KeyError:
            _log.info("'%s' skipped (missing '%s' attribute)", arg.name, name)
    return fun


class corrected_jack_frame(object):
    """Extracts frame counts from entries using jack_frame attribute.

    The jack_frame attribute is a 32-bit unsigned integer. This class converts
    this to an unsigned 64-bit integer, handling overflows. In order to do this
    correctly, entries must be called in order.

    """

    def __init__(self):
        from numpy import uint64, seterr
        seterr(over='ignore')   # ignore overflow warning
        self.frame = uint64()
        self.last = None

    def __call__(self, entry):
        """Return entry.attrs['jack_frame'] - first_entry.attrs['jack_frame']"""
        offset = entry.attrs['jack_frame']
        if self.last is not None:
            self.frame += offset - self.last
        self.last = offset
        return self.frame


def corrected_sampling_rate(keyed_entries):
    """Calculate the sampling rate relative to the system clock"""
    from arf import timestamp_to_float
    kf = attritemgetter('timestamp')
    entries = (keyed_entries[0], keyed_entries[-1])
    (s1, t1), (s2, t2) = ((s,timestamp_to_float(kf(e))) for s, e in entries)
    return (s2 - s1) / (t2 - t1)


def data_offset(entry_time, entry_ds, dset_time=0, dset_ds=None):
    """Return offset of a dataset in seconds, as either a float or a Fraction"""
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


def matches_entry(chunk, entry):
    """True if the timestamp and uuid attributes in chunk.data match entry"""
    from numpy import array_equal
    from uuid import UUID
    ret = array_equal(chunk.data.get('timestamp', None), entry.attrs['timestamp'])
    # COMPAT pre-2.0 doesn't have uuid
    try:
        ret &= arf.get_uuid(entry) == UUID(chunk.data['uuid'])
    except KeyError:
        pass


def dset_tags(dset):
    """Infer chunk tags based on dataset properties"""
    units = dset.attrs.get("units", None)
    if dset.dtype.names is not None:
        idx = dset.dtype.names.index("start")
        if idx < 0:
            raise ArfError("ARF compound dataset '%s' is missing a 'start' field" % dset.name)
        # 2.0 spec requires units for all fields, but older files only have one
        if not isinstance(units, basestring):
            units = units[idx]

    if units in ("s", "samples", "ms"):
        return tag_set("events")
    else:
        return tag_set("samples")


# Variables:
# End:
