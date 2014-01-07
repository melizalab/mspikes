# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility classes and functions for modules

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul  9 17:00:11 2013

"""
import contextlib
from mspikes.types import Node, tag_set
from mspikes.modules import dispatcher


def coroutine(func):
    from functools import wraps
    @wraps(func)
    def start(*args,**kwargs):
        cr = func(*args,**kwargs)
        cr.next()
        return cr
    return start


@coroutine
def visitor(func, pred=None):
    """A simple coroutine that calls func(obj) on each obj passed to send()

    If pred is non-none, only calls func(obj) if pred(obj) is true
    """
    try:
        while True:
            obj = (yield)
            if pred is None or pred(obj):
                func(obj)
    except GeneratorExit:
        pass


@coroutine
def print_progress():
    """Print progress of incoming chunks"""
    import sys
    last_offset = 0
    last_id = None
    try:
        while True:
            chunk = (yield)
            if chunk.offset > last_offset or chunk.id != last_id:
                sys.stderr.write("\r progress: [ t:{: >15.3f}s id:{: >15s} ]".format(float(chunk.offset),
                                                                                       chunk.id))
                sys.stderr.flush()
    except GeneratorExit:
        sys.stderr.write("\n")


@contextlib.contextmanager
def chain_modules(*modules):
    """A context manager that connects modules in sequence

    Example:
    >>> out = []
    >>> with chain_modules(module1, module2, visitor(out.append)) as chain: chain.send(data)

    """
    from mspikes.util import pair_iter

    for src,tgt in pair_iter(modules):
        src.add_target(tgt)

    yield modules[0]            # returns the context

    for src,tgt in pair_iter(modules):
        src._targets.remove((tgt, None))


@dispatcher.parallel("id","events","samples")
class splitter(Node):
    """Split chunks into smaller intervals

    This module is used to split long entries into more manageable chunks

    """
    nsamples = 65536            # likely to be 2-3 seconds at most sampling rates

    @classmethod
    def options(cls, addopt_f, **defaults):
        if "nsamples" not in defaults:
            addopt_f("--nsamples",
                     help="the maximum number of samples in a chunk (default %(default)d)",
                     type=int,
                     default=cls.nsamples,
                     metavar='INT')
        addopt_f("--start",
                 help="exclude data before %(metavar)s (default=%(default).1f)",
                 type=float,
                 default=0,
                 metavar='SEC')
        addopt_f("--stop",
                 help="exclude data after %(metavar)s (default None)",
                 type=float,
                 metavar='SEC')

    def __init__(self, name, **options):
        from mspikes import util
        Node.__init__(self, name)
        util.set_option_attributes(self, options, nsamples=4096, start=0., stop=None)
        self.last_time = 0

    def send(self, chunk):
        from arf import is_marked_pointproc
        from mspikes.util import to_seconds

        if "events" in chunk.tags:
            # point process data is sent in one chunk
            if self.start or self.stop:
                # filter out events outside requested times
                data_seconds = ((chunk.data['start'] if is_marked_pointproc(chunk.data)
                                 else chunk.data[:])
                                * (chunk.ds or 1.0) + chunk.offset)
                idx = data_seconds >= self.start
                if self.stop:
                    idx &= data_seconds <= self.stop
                if idx.sum() > 0:
                    # only emit chunk if there's data
                    chunk = chunk._replace(data=chunk.data[idx])
            Node.send(self, chunk)

        elif "samples" in chunk.tags:
            # check for overlap (within channel).
            if chunk.offset < self.last_time:
                self._log.warn("%s overlaps with previous dataset (end=%s)", chunk, self.last_time)

            # restrict by time
            nframes = chunk.data.shape[0]
            start, stop = time_series_offsets(chunk.offset, chunk.ds,
                                              self.start, self.stop, nframes)

            for i in xrange(start, stop, self.nsamples):
                t = to_seconds(i, chunk.ds, chunk.offset)
                data = chunk.data[slice(i, i + self.nsamples), ...]
                Node.send(self, chunk._replace(offset=t, data=data))

            self.last_time = to_seconds(nframes, chunk.ds, chunk.offset)


def timeseries_reader(array, ds, chunk_size, gap=0, id='', tags=tag_set("samples")):
    """Read chunks from a 1d time series array"""
    from numpy import array_split
    from mspikes.types import DataBlock
    from mspikes.util import to_seconds

    assert array.ndim == 1
    t = 0
    for arr in array_split(array, array.size / chunk_size):
        yield DataBlock(id, to_seconds(t, ds), ds, arr, tags)
        t += arr.size + gap


def pointproc_reader(array, ds, chunk_size, gap=0, id='', tags=tag_set("events")):
    """Read chunks from a 1d point process (unmarked) array"""
    from numpy import array_split
    from mspikes.types import DataBlock
    from mspikes.util import to_seconds

    assert array.ndim == 1
    if array.shape[0] < chunk_size:
        yield DataBlock(id, 0, ds, array, tags)
    else:
        for arr in array_split(array, array.shape[0] / chunk_size):
            yield DataBlock(id, to_seconds(arr[0], ds), ds, arr - arr[0], tags)


def time_series_offsets(dset_time, dset_ds, start_time, stop_time, nframes):
    """Calculate indices of start and stop times in a time series.

    For an array of nframes that begins at dset_time (seconds) and has samples
    spaced at dset_ds (samples/sec), returns the range of valid indices into the
    array, restricted between start_time and stop_time (in seconds).

    """
    start_idx = max(0, (start_time - dset_time) * dset_ds) if start_time else 0
    stop_idx = min(nframes, (stop_time - dset_time) * dset_ds) if stop_time else nframes

    return int(start_idx), int(stop_idx)


# Variables:
# End:
