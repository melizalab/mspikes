# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Basic types and concepts for mspikes.

"""
import abc
from collections import namedtuple

# simple immutable struct for transporting blocks of data
DataBlock = namedtuple("DataBlock", ("id", "offset", "dt", "data"))


class Node(object):
    """Represents a node in the mspikes processing graph."""

    @classmethod
    def options(cls, argfun, **defaults):
        """Add options for the Node to arggroup.

        argfun -- a closure with the same signature as
                  ArgumentParser.add_argument

        Additional keyword arguments contain parameters set in the node
        definition.

        """
        pass


class Source(Node):
    """A Node that produces data."""

    def add_sink(self, sink, filter):
        """Add a Sink that receives data from this node"""
        if not hasattr(self, "_sinks"): self._sinks = []
        self._sinks.append((sink, filter))

    def send(self, data):
        """Send a chunk of data to connected Sinks.

        Returns sequence of values from Sink.recv calls

        """
        return tuple(tgt.recv(data) for tgt,filt in self._sinks if filt(data))


class Sink(Node):
    """A Node that consumes data"""

    def recv(self, data):
        """Receive a chunk of data and process it."""
        pass


class IterableSource(Source):
    """A Source that can be iterated to read data from an external source"""

    def __iter__(self):
        """Process chunks of data and push them to downstream Nodes.

        Blocks until all downstream nodes have returned. Yields a tuple of the
        return values from all the downstream leaves.

        """
        return iter([])


class RandomAccessSource(IterableSource):
    """A Source that can be accessed using a time or channel mapping.

    Classes implementing this interface allow specific chunks to be requested
    using key-based access. The semantics for the key are as follows:

    __getitem__(number):  request data starting at <number> time
    __getitem__(slice(start, stop)): request data between start and stop
    __getitem__("channel"): request data from a specific channel

    Deriving classes may implement one or more of these interfaces.

    Returns an generator for the requested data.

    Example:
    for chunk in rsource[1000.0]: do_something

    """

    def __getitem__(self, key):
        """Returns an iterator yielding chunks referenced by key"""
        return iter([])


class Filter(Sink, Source):
    """A Node that consumes and produces data"""
    pass

# Variables:
# End:
