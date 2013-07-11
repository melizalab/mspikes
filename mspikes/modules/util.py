# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility classes and functions for modules

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul  9 17:00:11 2013
"""

import logging
import contextlib
from mspikes.types import Node

def coroutine(func):
    from functools import wraps
    @wraps(func)
    def start(*args,**kwargs):
        cr = func(*args,**kwargs)
        cr.next()
        return cr
    return start


@coroutine
def visitor(func):
    """A simple coroutine that calls func on each object passed to send()"""
    try:
        while True:
            func((yield))
    except GeneratorExit:
        pass


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

    yield modules[0]

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
                                * (chunk.dt or 1.0) + dset_time)
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
            start, stop = time_series_offsets(chunk.offset, chunk.dt, self.start, self.stop, nframes)

            for i in xrange(start, stop, self.nsamples):
                t = to_seconds(i, chunk.dt, chunk.offset)
                data = chunk.data[slice(i, i + self.nsamples), ...]
                Node.send(self, chunk._replace(offset=t, data=data))

            self.last_time = to_seconds(nframes, chunk.dt, chunk.offset)

        else:
            # pass on structure and other non-data chunks
            Node.send(self, chunk)


def time_series_offsets(dset_time, dset_dt, start_time, stop_time, nframes):
    """Calculate indices of start and stop times in a time series.

    For an array of nframes that begins at data_time (samples) with timebase
    offset_dt (samples/sec) and has samples spaced at dset_dt (samples/sec),
    returns the range of valid indices into the array, restricted between start_time
    and stop_time (in seconds).

    """
    start_idx = max(0, (start_time - dset_time) * dset_dt) if start_time else 0
    stop_idx = min(nframes, (stop_time - dset_time) * dset_dt) if stop_time else nframes

    return int(start_idx), int(stop_idx)


# Variables:
# End:
