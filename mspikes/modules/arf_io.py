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

    def __init__(self, filename, mode='r'):
        if isinstance(filename, h5py.File):
            self.file = filename
        else:
            self.file = arf.open_file(filename, mode)
        self._log = logging.getLogger("%s.%s" % (__name__, type(self).__name__))

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
        """Return a function that extracts offsets (in seconds) from entries

        Tries to use the most precise clock available

        use_timestamp -- force use of timestamp attribute even if sample count
                         attributes are present

        """
        keyname = "timestamp"
        sampling_rate = None
        fun = arf.entry_time

        if self.creator is None:
            self._log.info("couldn't determine ARF file source")
        elif use_timestamp:
            pass
        elif self.creator == 'arfxplog':
            keyname = "sample_count"
            sampling_rate = self.file.attrs['sampling_rate']
            fun = lambda entry: util.to_seconds(entry.attrs[keyname], sampling_rate)
        elif self.creator == 'jill':
            keyname = "jack_frame"
            def srate_visitor(name, obj):
                if isinstance(obj, h5py.Dataset):
                    # if None is returned the iteration will continue
                    return obj.attrs.get("sampling_rate", None)
            sampling_rate = self.file.visititems(srate_visitor)
            fun = corrected_jack_frame(sampling_rate)
        self._log.info("using '%s' attribute for time", keyname)
        if sampling_rate:
            self._log.info("file sampling rate (nominal): %d Hz", sampling_rate)
        return fun


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
                 action='append')
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
                 action='append')
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
        self._log.info("input file: %s", self.file.filename)

        try:
            self.chanp = util.any_regex(*options['channels'])
            self._log.info("only using channels that match %s", self.chanp.__doc__)
        except re.error, e:
            raise ValueError("bad channel regex: %s" % e.message)
        except (KeyError, TypeError):
            self.chanp = true_p

        try:
            self.entryp = util.any_regex(*options['entries'])
            self._log.info("only using entries that match %s", self.entryp.__doc__)
        except re.error, e:
            raise ValueError("bad entries regex: %s" % e.message)
        except (KeyError, TypeError):
            self.entryp = true_p


    def __iter__(self):
        """Iterate through the datasets.

        yields DataBlocks with the data field referencing the dataset object

        Datasets that don't match the entry and dataset selectors are skipped,
        as are datasets that have timebases inconsistent with the rest of the
        file.

        """
        to_seconds = self.get_offset_function(self.use_timestamp)
        if self.skip_sort:
            it = arf.keys_by_creation(self.file)
        else:
            it = sorted(self.file.keys(), key=lambda x: arf.entry_time(self.file[x]))

        entries = (self.file[name] for name in it
                   if self.entryp(name) and self.file.get(name, getclass=True) == h5py.Group)

        time_0 = None
        for entry in entries:
            # check for marked errors
            try:
                entry_time = to_seconds(entry)
                if time_0 is None:
                    time_0 = entry_time
                entry_time -= time_0
            except LookupError:
                self._log.info("'%s' skipped (no time attribute)", entry.name)
                continue

            if "jill_error" in entry.attrs:
                self._log.warn("'%s' was marked with an error: '%s'%s", entry.name, entry.attrs['jill_error'],
                          " (skipping)" if not self.use_xruns else "")
                if not self.use_xruns:
                    continue

            if self.start and entry_time < self.start:
                continue
            if self.stop and entry_time > self.stop:
                continue

            # emit structure blocks to indicate entry onsets
            chunk = DataBlock(id=entry.name,
                              offset=entry_time,
                              ds=None,
                              data=entry.attrs,
                              tags=tag_set("structure"))
            Node.send(self, chunk)
            yield chunk

            for id, dset in entry.iteritems():
                if not self.chanp(id):
                    continue
                dset_ds = dset.attrs.get('sampling_rate', None)
                dset_time = util.to_seconds(dset.attrs.get('offset', 0), dset_ds, entry_time)
                tags = dset_tags(dset)
                chunk = DataBlock(id=id, offset=dset_time, ds=dset_ds, data=dset, tags=tags)
                Node.send(self, chunk)
                yield chunk


class arf_writer(_base_arf, Node):
    """Write chunks to an ARF/HDF5 file. """

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to write (created if it doesn't exist)")
        addopt_f("--compress",
                 help="the compression level to use (default=%(default)d)",
                 default=defaults.get('compress', 9),
                 choices=range(10),
                 type=int,
                 metavar='INT')
        addopt_f("--auto-entry",
                 help="""turn on automatic generation of entries for all data and specify the base
                 name for automatically created entries. If this is set,
                 arf_writer will ignore any structure in the data or target
                 file.""",
                 default=defaults.get('auto_entry', None),
                 metavar='NAME',)

    can_store = staticmethod(filters.any_tag("samples", "events"))

    def __init__(self, filename, **options):
        util.set_option_attributes(self, options, compress=9, auto_entry=None,
                                   split_entry_template='%s_g%02d')
        _base_arf.__init__(self, filename, "a")
        self._log.info("output file: %s", self.file.filename)
        # build entry table
        self._offset_fun = self.get_offset_function()
        self._make_entry_table()
        arf.set_attributes(self.file, file_creator='mspikes.arf_writer')

    def send(self, chunk):
        if "structure" in chunk.tags and self.auto_entry is None:
            if chunk.id in self.file:
                entry = self.file[chunk.id]
                self._log.debug("structure chunk (id='%s', offset=%.2fs) matches existing entry '%s'",
                                chunk.id, chunk.offset, entry.name)
                if not matches_entry(chunk, entry):
                    raise ArfError("an entry named '%s' exists in the target file,"
                                   "but has the wrong timestamp or uuid", chunk.id)
                    # TODO ask the user to decide
            else:
                entry = self._create_entry(chunk.id, chunk.offset, **chunk.data)

        elif self.can_store(chunk):
            self._write_data(chunk)

    def _make_entry_table(self):
        """Generate a table of entries and start times."""
        entries = sorted(self.file.values(), key=arf.entry_time)

        self._offsets = []
        self._entries = []
        t0 = None
        for entry in entries:
            try:
                t = self._offset_fun(entry)
                if t0 is None:
                    t0 = t
                self._offsets.append(t - t0)
                self._entries.append(entry)
            except LookupError:
                pass

    def _create_entry(self, name, offset, **attributes):
        """Create a new entry in the target file

        Stores entry in the object's offset/entry table

        name -- the name of the entry
        offset -- the offset of the entry in the data stream

        Optional arguments:

        timestamp -- if supplied, the timestamp of the new entry in the arf file
                     is set to this. If not supplied, inferred from the
                     difference in seconds between offset and the closest entry.
                     If no entries in the file, the current time is used.

        Additional keyword arguments are set as attributes of the new entry

        """
        from numpy import searchsorted
        import datetime

        # match the entry against the entries in the file using the offset
        n_entries = len(self._offsets)
        idx = searchsorted(self._offsets, offset, side='right')
        try:
            timestamp = attributes.pop('timestamp')
        except KeyError:
            if n_entries == 0:
                # first entry in the file gets timestamp of now
                timestamp = datetime.datetime.now()
            else:
                # calculate timestamp from offset with existing entry
                other = self._entries[idx] if idx < n_entries else self._entries[n_entries - 1]
                timestamp = (arf.timestamp_to_float(other.attrs['timestamp']) +
                             offset - self._offset_fun(other))
        self._log.info("created new entry '%s' (offset=%.2fs)", name, float(offset))
        entry = arf.create_entry(self.file, name, timestamp, **attributes)
        # insert new entry in the table of entries
        self._offsets.insert(idx, offset)
        self._entries.insert(idx, entry)
        return entry

    def _next_entry(self, entry, offset):
        """Create the next entry in a series."""
        import re

        idx = 0
        if self.auto_entry is not None:
            # automatically generating numbered entries
            if entry is None:
                idx = 0
            else:
                idx = int(re.match(r"/%s_(\d+)" % self.auto_entry, entry.name).group(1))
            new_name = "%s_%05d" % (self.auto_entry, idx + 1)
            attrs = dict()
        else:
            # adding an additional entry because of a gap in a sampled data
            # stream
            try:
                base = entry.attrs['mspikes_base_entry']
                idx = int(re.match(r"%s_(\d+)" % base, entry.name).group(1))
            except KeyError:
                base = entry.name
                idx = 0
            attrs = dict(mspikes_base_entry=entry.name)
            new_name = "%s_%03d" % (base, idx + 1)
        return self._create_entry(new_name, offset, **attrs)

    def _write_data(self, chunk):
        """Look up target dataset for chunk and write data.

        Creates new datasets as needed, and may create a new entry if there is a gap.

        """
        from mspikes.types import DataError
        from numpy import searchsorted

        # Look up target entry. TODO more efficient algorithm? check most
        # recently used entry first to avoid searching? use a dict for exact
        # time lookups?
        idx = searchsorted(self._offsets, chunk.offset, side='right')
        if idx == 0:
            if self.auto_entry is None:
                raise ArfError("unable to find a target entry with offset < %.2f" % float(chunk.offset))
            else:
                raise NotImplementedError("need to use auto_entry to create new entry")
        else:
            entry = self._entries[idx - 1]
            entry_time = self._offsets[idx - 1]
        self._log.debug("chunk (id='%s', offset=%.2fs) matches '%s' (offset=%.2fs)",
                        chunk.id, float(chunk.offset), entry.name, entry_time)

        # either append data to an existing dataset or create a new dataset
        data_offset = chunk.offset - entry_time
        if chunk.ds is not None:
            data_offset = util.to_samples(data_offset, chunk.ds)
        try:
            dset = entry[chunk.id]
            # make sure this is a good idea
            if dset.attrs.get('sampling_rate', None) != chunk.ds:
                raise DataError("sampling rate of (id='%s', offset=%.3fs) mismatches target dataset '%s'" %
                                (chunk.id, float(chunk.offset), dset.name))
            dset_offset = dset.attrs.get('offset', 0)

            if data_offset == dset_offset:
                raise DataError("trying to write (id='%s', offset=%.3fs) to existing dataset '%s'" %
                                (chunk.id, float(chunk.offset), dset.name))
                # TODO allow user to override

            # additional steps to verify alignment for sampled data
            if "samples" in chunk.tags:
                gap = data_offset - (dset_offset + dset.size)
                if gap < 0:
                    raise DataError("chunk (id='%s', offset=%.3f) overlaps with an existing dataset '%s'" %
                                    (chunk.id, float(chunk.offset), dset.name))
                    # TODO allow user to override?
                elif gap > 0:
                    # store data in a subsequent entry
                    self._log.info("gap in data '%s' (offset='%.3fs) requires new entry" %
                                   (chunk.id, float(chunk.offset)))
                    entry = self._next_entry(entry, chunk.offset)
                    data_offset = 0
                    raise KeyError   # goto new dataset condition
            # append data
            arf.append_data(dset, chunk.data)

        except KeyError:
            # create a new dataset; set chunk size and max shape based on data
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
            arf.create_dataset(entry, chunk.id, chunk.data, units=units,
                               chunks=chunks, maxshape=maxshape, compression=self.compress,
                               sampling_rate=chunk.ds, offset=data_offset)


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
    kf = attritemgetter('timestamp')
    entries = (keyed_entries[0], keyed_entries[-1])
    (s1, t1), (s2, t2) = ((s, arf.timestamp_to_float(kf(e))) for s, e in entries)
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
    # Compat pre-2.0 doesn't have uuid
    try:
        ret &= arf.get_uuid(entry) == UUID(chunk.data['uuid'])
    except KeyError:
        pass
    return ret


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
