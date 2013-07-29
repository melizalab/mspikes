# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions and classes for reading and writing ARF files.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import logging
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

    def __init__(self, filename, mode='r+', dry_run=False):
        self._log = logging.getLogger("%s.%s" % (__name__, type(self).__name__))
        file_options = {}
        if dry_run:
            file_options = {'driver': 'core', 'backing_store': False}
        if isinstance(filename, h5py.File):
            self.file = filename
        else:
            self.file = arf.open_file(filename, mode, **file_options)
        try:
            arf.check_file_version(self.file)
        except Warning, w:
            self._log.warn("%s", w)

    def get_creator(self):
        """The program that created the file, or None if unknown"""
        if self.file.attrs.get('program', None) == 'arfxplog':
            return 'arfxplog'
        entry = get_first(self.file, h5py.Group)
        if entry and "jack_frame" in entry.attrs:
            return "jill"
        else:
            return self.file.attrs.get('file_creator', None)

    def get_offset_function(self, use_timestamp=False):
        """Return a function that extracts offsets (in seconds) from entries

        Tries to use the most precise clock available

        use_timestamp -- force use of timestamp attribute even if sample count
                         attributes are present

        """
        keyname = "timestamp"
        sampling_rate = None
        fun = arf_entry_time

        creator = self.get_creator()
        if creator is None:
            self._log.info("couldn't determine ARF file source")
        elif use_timestamp:
            pass
        elif creator == 'arfxplog':
            keyname = "sample_count"
            sampling_rate = self.file.attrs['sampling_rate']
            fun = lambda entry: util.to_seconds(entry.attrs[keyname], sampling_rate)
        elif creator == 'jill':
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

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
        Node.close(self)


class arf_reader(_base_arf, RandomAccessSource):
    """Source data from an ARF/HDF5 file

    emits:  _events (point process datasets)
            _samples (time series datasets)
            _structure (entry start times)

    Iterates through _entries of the file in temporal order, emitting chunks
    separately for each dataset in the _entries. By default the timestamp of the
    _entries is used to calculate offsets for the chunks, but for ARF files
    created by 'arfxplog' and 'jrecord' the sample clock can be used as well.

    To only read specific entries or channels, you can use the --entries or
    --channels options. Note that these options are interpreted as regular
    expressions.

    """
    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("filename",
                 help="the file to read")
        addopt_f("--channels",
                 help="""regular expression restricting which channels to read (default all). For
        example, 'pcm_000' will only match channels that start with 'pcm_000',
        including 'pcm_000' but also 'pcm_0001', etc. To match 'pcm_000'
        exactly, use 'pcm_000$'. You can also exclude specific channels using
        regular expressions. '(?!pcm_000)' will match any channel that doesn't
        start with 'pcm_000'. If multiple patterns are specified, channels that
        match any pattern will be included.""",
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
                 help="regular expression restricting which entries to read (default all)",
                 metavar='P',
                 action='append')
        # TODO select based on datatype attribute
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
            it = sorted(self.file.keys(), key=lambda x: arf_entry_time(self.file[x]))

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
                          " (skipping)" if not self.ignore_xruns else "")
                if not self.ignore_xruns:
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
                if dset.size == 0:
                    continue
                if 'sampling_rate' in dset.attrs:
                    dset_ds = dset.attrs['sampling_rate']
                    # python 2.6 shim
                    if hasattr(dset_ds, 'dtype') and dset_ds.dtype.kind == 'i':
                        dset_ds = int(dset_ds)
                else:
                    dset_ds = None
                dset_offset = dset.attrs.get('offset', 0)
                if dset_offset > 0:
                    dset_time = util.to_seconds(dset_offset, dset_ds, entry_time)
                else:
                    dset_time = entry_time
                tags = dset_tags(dset)
                # don't read data until necessary: preserving the dtypes can help downstream
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
        addopt_f("--dry-run",
                 help="do everything but actually write to the file",
                 action="store_true")

    can_store = staticmethod(filters.any_tag("samples", "events"))

    def __init__(self, filename, **options):
        util.set_option_attributes(self, options, compress=9, auto_entry=None,
                                   split_entry_template='%s_g%02d',
                                   dry_run=False)
        try:
            _base_arf.__init__(self, filename, "a", dry_run=self.dry_run)
        except IOError:
            raise ArfError("Error writing to '%s' - are you trying to write to the source file?" %
                           filename)
        self._log.info("output file: %s %s", self.file.filename, "(DRY RUN)" if self.dry_run else "")
        # build entry table
        self._offset_fun = self.get_offset_function()
        self._make_entry_table()
        arf.set_attributes(self.file, file_creator='mspikes.arf_writer', overwrite=False)

    def send(self, chunk):
        if "structure" in chunk.tags and self.auto_entry is None:
            if chunk.id in self.file:
                entry = self.file[chunk.id]
                self._log.debug("structure chunk (id='%s', offset=%.2fs) matches existing entry '%s'",
                                chunk.id, float(chunk.offset), entry.name)
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
        entries = sorted(self.file.values(), key=arf_entry_time)
        self._offsets = []
        self._entries = []
        self._datasets = set()
        t0 = None
        for entry in entries:
            try:
                t = self._offset_fun(entry)
            except LookupError:
                pass
            else:
                if t0 is None:
                    t0 = t
                self._offsets.append(t - t0)
                self._entries.append(entry)
                self._datasets.update(dset.name for dset in entry.itervalues()
                                      if isinstance(dset, h5py.Dataset))


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
        # TODO store mspikes offset in entry in some unambiguous format
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
            # adding an additional entry because of gap in sampled data stream
            try:
                base = entry.attrs['mspikes_base_entry']
                idx = int(re.match(r"%s_(\d+)" % base, entry.name).group(1))
            except KeyError:
                base = entry.name
                idx = 0
            attrs = dict(mspikes_base_entry=base)
            new_name = "%s_%03d" % (base, idx + 1)
        if new_name in self.file:
            return self.file[new_name]
        else:
            return self._create_entry(new_name, offset, **attrs)

    def _write_data(self, chunk):
        """Look up target dataset for chunk and write data.

        Creates new datasets as needed, and may create a new entry if there is a gap.

        """
        from numpy import searchsorted

        # Look up target entry
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

        # offset of data in entry
        data_offset = chunk.offset - entry_time
        if chunk.ds is not None:
            data_offset = util.to_samples(data_offset, chunk.ds)
        else:
            data_offset = float(data_offset)

        if chunk.id not in entry:
            dset = self._create_dataset(entry, chunk, data_offset)
            dset_offset = data_offset
        else:
            dset = entry[chunk.id]
            dset_offset = dset.attrs.get('offset', 0)
            # make sure this is a good idea. most errors will be caught by this
            # first check
            if dset.name in self._datasets:
                raise ArfError("(id='%s', offset=%.3f): not written; dataset '%s' already exists" %
                               (chunk.id, float(chunk.offset), dset.name))
                return
            if dset.maxshape[0] is not None:
                raise ArfError("(id='%s', offset=%.3fs): target dataset '%s' is not extensible" %
                               (chunk.id, float(chunk.offset), dset.name))
            if dset.attrs.get('sampling_rate', None) != chunk.ds:
                raise ArfError("(id='%s', offset=%.3fs): samplerate mismatches target dataset '%s'" %
                               (chunk.id, float(chunk.offset), dset.name))
            if "samples" in chunk.tags:
                # additional steps to verify alignment for sampled data
                gap = data_offset - (dset_offset + dset.size)
                if gap < 0:
                    raise ArfError("(id='%s', offset=%.3f): overlaps with an existing dataset '%s'" %
                                    (chunk.id, float(chunk.offset), dset.name))
                elif gap > 0:
                    # store data in a subsequent entry if there's a gap
                    self._log.info("(id='%s', offset='%.3fs): gap in data requires new entry",
                                   chunk.id, float(chunk.offset))
                    entry = self._next_entry(entry, chunk.offset)
                    data_offset = dset_offset = 0
                    dset = self._create_dataset(entry, chunk, data_offset)

        if "samples" in chunk.tags or isinstance(chunk.data, h5py.Dataset):
            # no need to split data that come from another arf file
            arf.append_data(dset, chunk.data)
        elif "events" in chunk.tags:
            try:
                next_entry_time = self._offsets[idx]
            except IndexError:
                data = chunk.data
                next = None
            else:
                data, next = _split_point_process(chunk.data, data_offset, dset_offset,
                                                  next_entry_time - entry_time, chunk.ds)
            if data.size:
                arf.append_data(dset, data)
            else:
                # somewhat hacky to delete empty dataset, but logic is complex otherwise
                del entry[dset.name]
            if next is not None and next.size > 0:
                self.send(chunk._replace(offset=next_entry_time, data=next))


    def _create_dataset(self, entry, chunk, data_offset):
        """Create a new empty dataset"""
        # create a new dataset; set chunk size and max shape based on data
        if "samples" in chunk.tags:
            chunks = chunk.data.shape
            units = ''
        elif "events" in chunk.tags:
            # auto-chunk size for point process
            chunks = True
            units = 's' if chunk.ds is None else 'samples'
            if chunk.data.dtype.names is not None:
                # compound dtype requires units for each field
                units = tuple((units if x == 'start' else '') for x in chunk.data.dtype.names)
        else:
            raise RuntimeError("no logic for storing data with tags %s" % tuple(chunk.tags))
        maxshape = (None,) + chunk.data.shape[1:]
        shape = (0,) + chunk.data.shape[1:]
        dset = entry.create_dataset(chunk.id, dtype=chunk.data.dtype, shape=shape, maxshape=maxshape,
                                    chunks=chunks, compression=self.compress)
        arf.set_attributes(dset, units=units, datatype=arf.DataTypes.UNDEFINED,
                           sampling_rate=chunk.ds, offset=data_offset)
        return dset


def true_p(*args):
    return True


class corrected_jack_frame(object):
    """Extracts frame counts from entries using jack_frame attribute.

    The jack_frame attribute is a 32-bit unsigned integer. This class converts
    this to an unsigned 64-bit integer, handling overflows. In order to do this
    correctly, entries must be called in order.

    """
    def __init__(self, sampling_rate):
        from numpy import uint64, seterr
        seterr(over='ignore')   # ignore overflow warning
        self.sampling_rate = int(sampling_rate)
        self.frame = uint64()
        self.last = None

    def __call__(self, entry):
        """Return entry.attrs['jack_frame'] - first_entry.attrs['jack_frame']"""
        from fractions import Fraction
        offset = entry.attrs['jack_frame']
        if self.last is not None:
            self.frame += offset - self.last
        self.last = offset
        return Fraction(long(self.frame), self.sampling_rate)


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


def _split_point_process(data, data_offset, dset_offset, entry_offset=None, data_ds=None):
    """Split point process data across entry boundary.

    data - an array of times, or a structured array with 'start' field
    data_offset - the offset of the data times, relative to the start of the current entry
    dset_offset - the offset of the target dataset
    entry_offset - the offset of the next entry, relative to the current one,
                   *in seconds*. If None, the data is not split

    All offset values need to be in the same timebase as the times in data,
    except for entry_offset, which is converted using data_ds

    """
    from numpy import ones
    data = data.copy()
    is_struct = data.dtype.fields is not None
    times = data['start'] if is_struct else data

    # first adjust times relative to entry start
    times += data_offset
    # then determine when/if the data should be cut, adjusting for sampling rate
    if entry_offset is not None:
        entry_offset *= data_ds or 1.0
        idx = times < entry_offset
        # times for current entry are relative to dset_offset
        times[idx] -= dset_offset
        # times for next entry are relative to entry_offset
        times[~idx] -= entry_offset
    else:
        idx = ones(times.size, dtype='bool')
        times -= dset_offset

    return data[idx], data[~idx]


def get_first(obj, obj_type):
    """Return the first element of obj_type under obj"""
    def visit(name):
        if obj.get(name, getclass=True) is obj_type:
            return obj.get(name)
    return obj.visit(visit)


def arf_entry_time(entry):
    """Get timestamp of an entry in floating point format, or None if not set"""
    try:
        return arf.timestamp_to_float(entry.attrs['timestamp'])
    except KeyError:
        return None


# Variables:
# End:
