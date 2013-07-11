# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility classes and functions for modules

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul  9 17:00:11 2013
"""

import logging
import contextlib
from mspikes.types import Node, tag_set

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
                sys.stdout.write("\r progress: [ t:{: >15.3f}s id:{: >15s} ]".format(float(chunk.offset),
                                                                                       chunk.id))
                sys.stdout.flush()
    except GeneratorExit:
        sys.stdout.write("\n")


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


class splitter(Node):
    """Split chunks into smaller intervals

    This module is used to split long entries into more manageable chunks

    """
    nsamples = 4096
    _log = logging.getLogger(__name__ + ".arf_reader")

    @classmethod
    def options(cls, addopt_f, **defaults):
        if "nsamples" not in defaults:
            addopt_f("nsamples",
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

    def __init__(self, **options):
        from mspikes import util
        from collections import defaultdict
        util.set_option_attributes(self, options, start=0., stop=None)

        self.last_time = 0

    def send(self, chunk):
        from mspikes.util import to_seconds

        if "events" in chunk.tags:
            # point process data is sent in one chunk
            if self.start or self.stop:
                # filter out events outside requested times
                data_seconds = ((chunk.data['start'] if chunk.data.dtype.names else chunk.data[:])
                                * (chunk.ds or 1.0) + dset_time)
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
                self._log.warn("'%s' (start=%s) overlaps with previous dataset (end=%s)",
                          chunk.id, chunk.offset, self.last_time)

            # restrict by time
            nframes = chunk.data.shape[0]
            start, stop = time_series_offsets(chunk.offset, chunk.ds, self.start, self.stop, nframes)

            for i in xrange(start, stop, self.nsamples):
                t = to_seconds(i, chunk.ds, chunk.offset)
                data = chunk.data[slice(i, i + self.nsamples), ...]
                Node.send(self, chunk._replace(offset=t, data=data))

            self.last_time = to_seconds(nframes, chunk.ds, chunk.offset)

        else:
            # pass on structure and other non-data chunks
            Node.send(self, chunk)


def array_reader(array, ds, chunk_size, id='', tags=tag_set("samples")):
    """Generate chunks from a 1d array"""
    from mspikes.types import DataBlock
    from mspikes.util import to_seconds

    assert array.ndim == 1
    for i in xrange(0, array.size, chunk_size):
        yield DataBlock(id, to_seconds(i, ds), ds, array[i:i + chunk_size], tags)


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
