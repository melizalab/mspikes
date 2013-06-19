# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Basic types and concepts for mspikes.

"""
import abc
from collections import namedtuple

# simple immutable struct for passing data
data_chunk = namedtuple("data_chunk",
                        ("id", "offset", "dt", "data"))


class Node:
    """Represents a node in the mspikes processing graph."""
    __metaclass__ = abc.ABCMeta

    @classmethod
    def descr(cls):
        """Return a brief description of the module"""
        raise NotImplementedError

    @classmethod
    def options(cls, arggroup, prefix=None):
        """Add options for the module to arggroup.

        arggroup -- an instance of argparse.ArgumentParser
        prefix   -- if not None, prefix arguments with this string
        """
        raise NotImplementedError


class Source(Node):
    """A Node that produces data."""
    _targets = []

    @abc.abstractproperty
    def targets(self):
        """The (mutable) sequence of (Sink,data_filter) links for this node."""
        return self._targets


class Sink(Node):
    """A Node that consumes data"""

    @abc.abstractmethod
    def __call__(self, chunk):
        """Push a chunk of data to the module for processing.

        Raises ValueError if the data are of the wrong type.

        """
        raise NotImplementedError


class IterableSource(Source):
    """A Source that can be iterated to read data from an external source"""

    @abc.abstractmethod
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
    @abc.abstractmethod
    def __getitem__(self, key):
        """Returns an iterator yielding chunks referenced by key"""
        return iter([])


class Filter(Sink, Source):
    """A Node that consumes and produces data"""
    pass


# Variables:
# End:
