# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions and classes for reading and writing ARF files.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 14:50:02 2013
"""
import h5py
import arf

from mspikes import __version__
from mspikes import util
from mspikes import filters
from mspikes.types import DataBlock, Node, RandomAccessSource, tag_set, MspikesError


class ArfError(MspikesError):
    """Raised for errors reading or writing ARF files"""
    pass


class _base_arf(object):
    """Base class for arf reader and writer"""

    def __init__(self, name, filename, mode='r+', dry_run=False):
        Node.__init__(self, name)
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

    def __del__(self):
        try:
            self.file.close()
            self.file = None
        except:
            pass
        Node.__del__(self)


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
        addopt_f("--use-timestamp", help="""use entry timestamp for timebase and
        ignore other fields. May lead to
        warnings about data overlap because of jitter in the system clock. Using
        sample-based times from files recorded at multiple sampling rates or
        different clock start times may lead to undefined behavior""",
                 action='store_true')
        addopt_f("--ignore-xruns",
                 help="use entries with xruns or other errors (default is to skip)",
                 action='store_true')

    def __init__(self, name, filename, **options):
        import re
        util.set_option_attributes(self, options,
                                   start=0, stop=None,
                                   use_timestamp=False,
                                   ignore_xruns=False,
                                   skip_sort=False)
        _base_arf.__init__(self, name, filename, "r")
        self._log.info("input file: '%s'", self.file.filename)
        for k in self.file.attrs:
            self._log.info("file attribute: %s=%s", k, self.file.attrs[k])

        try:
            self.chanp = util.any_regex(*options['channels'])
            self._log.info("only using channels that match %s", self.chanp.__doc__)
        except re.error, e:
            raise ValueError("bad channel regex: %s" % e.message)
        except (KeyError, TypeError):
            self.chanp = util.true_p

        try:
            self.entryp = util.any_regex(*options['entries'])
            self._log.info("only using entries that match '%s'", self.entryp.__doc__)
        except re.error, e:
            raise ValueError("bad entries regex: %s" % e.message)
        except (KeyError, TypeError):
            self.entryp = util.true_p


    def __iter__(self):
        """Iterate through the datasets.

        yields DataBlocks with the data field referencing the dataset object

        Datasets that don't match the entry and dataset selectors are skipped,
        as are datasets that have timebases inconsistent with the rest of the
        file.

        """
        from mspikes import register
        self._log.info("sorting entries")
        entries = sorted((v for v in self.file.itervalues() if isinstance(v, h5py.Group)),
                         key=arf_entry_time)

        to_seconds = entry_offset_calculator(self.use_timestamp)
        for entry in entries:
            # check for marked errors
            try:
                entry_time, entry_ds = to_seconds(entry)
            except AttributeError:
                self._log.info("'%s' skipped (no time attribute)", entry.name)
                continue

            if "jill_error" in entry.attrs:
                self._log.warn("'%s' was marked with an error: '%s'%s",
                               entry.name, entry.attrs['jill_error'],
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
                              ds=entry_ds,
                              data=entry.attrs,
                              tags=tag_set("structure"))
            Node.send(self, chunk)
            yield chunk

            for id in sorted(entry, key=util.natsorted):
                dset = entry[id]
                if not self.chanp(id):
                    continue
                if dset.shape[0] == 0:
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
                try:
                    register.add_id(id, **dset.attrs)
                except NameError:
                    pass
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
        addopt_f("--dry-run",
                 help="do everything but actually write to the file",
                 action="store_true")
        addopt_f("--overwrite",
                 help="overwrite existing datasets (default is to raise error)",
                 action='store_true')

    can_store = staticmethod(filters.any_tag("samples", "events"))

    def __init__(self, name, filename, **options):
        util.set_option_attributes(self, options, compress=9, auto_entry=None,
                                   split_entry_template='%s_g%02d',
                                   dry_run=False, overwrite=False)
        try:
            _base_arf.__init__(self, name, filename, "a", dry_run=self.dry_run)
        except IOError:
            raise ArfError("Error writing to '%s' - are you trying to write to the source file?" %
                           filename)
        self._log.info("output file: %s %s", self.file.filename, "(DRY RUN)" if self.dry_run else "")
        # build entry table
        self._make_entry_table()
        arf.set_attributes(self.file,
                           file_creator='org.meliza.mspikes/arf_writer ' + __version__,
                           overwrite=False)

    def send(self, chunk):
        if "structure" in chunk.tags:
            self._write_structure(chunk)
        elif "samples" in chunk.tags:
            self._write_samples(chunk)
        elif "events" in chunk.tags:
            self._write_events(chunk)
        else:
            self._log.debug("%s skipped: data type not supported", chunk)

    def _write_structure(self, chunk):
        """ Write a structure chunk to the file; creates entries as needed if auto_entry is off"""
        from bisect import bisect
        import datetime
        if self.auto_entry is not None:
            self._log.debug("%s skipped: auto_entry is true", chunk)
            return

        if chunk.id in self.file:
            # see if the entry exists
            entry = self.file[chunk.id]
            if not matches_entry(chunk, entry):
                raise ArfError("an entry named '%s' exists in the target file,"
                               "but has the wrong timestamp or uuid", chunk.id)
                # TODO ask the user to decide
            self._log.debug("%s matches existing entry '%s'", chunk, entry.name)
        else:
            # create a new entry in the file with the chunk's offset and attributes
            attrs = dict(chunk.data)
            # need to find the closest entry to insert into list
            n_entries = len(self._offsets)
            idx = bisect(self._offsets, chunk.offset)
            try:
                # use chunk timestamp if it exists
                timestamp = attrs.pop('timestamp')
            except KeyError:
                # otherwise infer from other entries in file
                if n_entries == 0:
                    # first entry in the file gets timestamp of now
                    timestamp = datetime.datetime.now()
                else:
                    # calculate timestamp from offset with existing entry
                    o_idx = idx if idx < n_entries else n_entries - 1
                    timestamp = (arf.timestamp_to_float(self._entries[o_idx].attrs['timestamp']) +
                                 chunk.offset - self._offsets[o_idx])
            # set creator and sample count attribute
            if 'entry_creator' not in attrs:
                attrs['entry_creator'] = 'org.meliza.mspikes/arf_writer ' + __version__
            if chunk.ds is not None:
                if 'sample_count' not in attrs:
                    attrs['sample_count'] = long(chunk.offset * chunk.ds)
                if 'sampling_rate' not in attrs:
                    attrs['sampling_rate'] = chunk.ds

            # create entry and insert in the table of entries
            entry = arf.create_entry(self.file, chunk.id, timestamp, **attrs)
            self._offsets.insert(idx, chunk.offset)
            self._entries.insert(idx, entry)
            self._log.info("created new entry '%s' (offset=%.2fs)", chunk.id, float(chunk.offset))

    def _write_samples(self, chunk):
        """Writes sampled data to the file.

        Uses the entry with offset closest and less than chunk offset, or raises
        an error if no such entry exists. An error is also raised if the entry
        already has a dataset and there's a gap between it and the data in the
        chunk.

        """
        from bisect import bisect
        idx = bisect(self._offsets, chunk.offset)
        if idx == 0:
            raise ArfError("no entry with offset < %.2f in file" % float(chunk.offset))
        entry = self._entries[idx - 1]
        entry_time = self._offsets[idx - 1]

        self._log.debug("%s matches '%s' (offset=%.2fs)", chunk, entry.name, entry_time)
        # offset of data in entry
        data_offset = util.to_samp_or_sec(chunk.offset - entry_time, chunk.ds)
        dset = self._require_dataset(entry, chunk, data_offset)
        dset_offset = dset.attrs.get('offset', 0)

        # check whether there's a gap between existing data and new chunk
        gap = data_offset - (dset_offset + dset.shape[0])
        if gap != 0:
            raise ArfError("%s not contiguous with existing dataset '%s' (gap=%d samples)" %
                           (chunk, dset.name, gap))
        arf.append_data(dset, chunk.data)

    def _write_events(self, chunk):
        """Writes event data in chunk to the file """
        # Event data may or may not be divided into chunks that correspond to
        # entries in the target file. Therefore the event times have to be
        # compared against the offsets of the entries and split accordingly. A
        # recursive algorithm (store data for current entry and then recurse
        # with remainder) fails if there are many entries and the call stack
        # gets too deep, so the chunk has to be subdivided and dealt with
        # iteratively. The data stream must be ordered.
        from itertools import imap, repeat

        # split data by entries
        data = util.event_offset(chunk.data, util.to_samp_or_sec(chunk.offset, chunk.ds))
        cuts = imap(util.to_samp_or_sec, self._offsets, repeat(chunk.ds))

        for cut_idx, subset in util.cutarray(util.event_times(data), cuts):
            cut_idx = max(cut_idx, 0)
            entry = self._entries[cut_idx]
            entry_offset = util.to_samp_or_sec(self._offsets[cut_idx], chunk.ds)
            dset = self._require_dataset(entry, chunk, 0)
            dset_offset = dset.attrs.get('offset', 0)
            events = util.event_offset(data[subset], -entry_offset - dset_offset)
            self._log.debug("%d events match '%s' (offset=%.2fs)",
                            events.size, entry.name, entry_offset)
            arf.append_data(dset, events)

    def _make_entry_table(self):
        """Generates a table of existing entries and their start times."""
        self._log.info("scanning existing entries and datasets")
        entries = sorted((v for v in self.file.itervalues() if isinstance(v, h5py.Group)),
                         key=arf_entry_time)
        self._offsets = []
        self._entries = []
        self._datasets = set()
        to_seconds = entry_offset_calculator()
        for entry in entries:
            try:
                entry_time, entry_ds = to_seconds(entry)
            except AttributeError:
                pass
            else:
                self._offsets.append(entry_time)
                self._entries.append(entry)
                self._datasets.update(dset.name for dset in entry.itervalues()
                                      if isinstance(dset, h5py.Dataset))

    def _require_dataset(self, entry, chunk, data_offset):
        """Returns the dataset corresponding to chunk.id in entry.

        If the entry does not exist, it's created, using attributes and data
        type from chunk. The data contents of the chunk aren't used.

        """
        from mspikes import register
        import posixpath as pp
        dset_name = pp.join(entry.name, chunk.id)
        if chunk.id in entry and dset_name in self._datasets:
            # if dataset existed when the file was opened, overwrite or error
            if self.overwrite:
                del entry[chunk.id]
                self._datasets.remove(dset_name)
            else:
                raise ArfError("%s not written: dataset '%s' already exists" %
                               (chunk, dset_name))
        if chunk.id in entry:
            dset = entry[chunk.id]
            # check if the upstream provider is insane and changed the sampling rate
            if dset.attrs.get('sampling_rate', None) != chunk.ds:
                raise ArfError("%s samplerate mismatches target dataset '%s'" %
                               (chunk, dset.name))
            return dset

        # create a new dataset; set chunk size and max shape based on data
        if "samples" in chunk.tags:
            chunks = chunk.data.shape
            units = ''
        elif "events" in chunk.tags:
            # auto-chunk size for point process
            chunks = True
            units = 's' if chunk.ds is None else 'samples'
            if arf.is_marked_pointproc(chunk.data):
                # compound dtype requires units for each field
                units = tuple((units if x == 'start' else '') for x in chunk.data.dtype.names)
        else:
            raise RuntimeError("no logic for storing data with tags %s" % tuple(chunk.tags))
        maxshape = (None,) + chunk.data.shape[1:]
        shape = (0,) + chunk.data.shape[1:]
        dset = entry.create_dataset(chunk.id, dtype=chunk.data.dtype,
                                    shape=shape, maxshape=maxshape,
                                    chunks=chunks, compression=self.compress)
        attrs = register.get_by_id(chunk.id)
        attrs.update(sampling_rate=chunk.ds, offset=data_offset, units=units)
        arf.set_attributes(dset, **attrs)
        return dset


class entry_offset_calculator(object):
    """Calculates the offset, in seconds, of an arf entry.

    Attempts to use sample counts if they're present, falling back to the
    timestamp. The offsets are referenced to that of the first entry passed to
    the object, and corrected for overflows.

    """

    def __init__(self, use_timestamp=False):
        """ Initialize the calculator. If use_timestamp is true, ignores sample count attributes """
        from numpy import seterr
        seterr(over='ignore')   # ignore overflow warning
        self.use_timestamp = use_timestamp

    def __call__(self, entry):
        """Calculate interval in seconds between first entry and argument.

        If sample count information is available, returns (interval,
        sampling_rate), with interval as a Fraction. If not available or if the
        object was initialized with use_timestamp=True, returns (interval,
        None), with interval as a float.

        """
        from numpy import zeros_like, int64
        from fractions import Fraction

        sampling_rate = None
        if self.use_timestamp:
            pass
        elif 'sample_count' in entry.attrs:
            # arfxplog and mspikes files
            t = entry.attrs['sample_count']
            try:
                sampling_rate = entry.attrs['sampling_rate']
            except KeyError:
                try:
                    sampling_rate = entry.file.attrs['sampling_rate']
                except KeyError:
                    pass
        elif 'jack_frame' in entry.attrs:
            # jill files
            t = entry.attrs['jack_frame']
            try:
                sampling_rate = entry.attrs['jack_sampling_rate']
            except KeyError:
                dset = get_first(entry, h5py.Dataset)
                try:
                    sampling_rate = dset.attrs['sampling_rate']
                except KeyError:
                    pass
        # fallback to timestamp
        if sampling_rate is None:
            t = entry.attrs['timestamp']

        # this block corrects for overflow of 32-bit counters by calculating the
        # difference between the current time and the last time and adding it to
        # a variable with a larger type
        try:
            self.current += t - self.last
        except AttributeError:
            self.current = zeros_like(t)
            if self.current.dtype.kind == 'i' and self.current.dtype.itemsize < 8:
                self.current = self.current.astype(int64)
        self.last = t

        if sampling_rate is None:
            return arf.timestamp_to_float(self.current), None
        else:
            return Fraction(long(self.current), long(sampling_rate)), sampling_rate


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
    if arf.is_marked_pointproc(dset):
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


def get_first(obj, obj_type):
    """Returns the first element of obj_type under obj"""
    def visit(name):
        if obj.get(name, getclass=True) is obj_type:
            return obj.get(name)
    return obj.visit(visit)


def arf_entry_time(entry):
    """Returns timestamp of entry in floating point format, or None if not set"""
    try:
        return arf.timestamp_to_float(entry.attrs['timestamp'])
    except KeyError:
        return None


# Variables:
# End:
