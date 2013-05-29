# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Basic types and concepts for mspikes.

"""
from collections import namedtuple
from abc import ABCMeta, abstractmethod

# simple immutable structs for passing data
data_chunk = namedtuple("data_chunk",
                        ("channel", "offset", "sampling_rate", "data"))


class Node:
    """Represents a node in the mspikes processing graph.

    An interface for generating documentation and commandline options.

    """
    __metaclass__ = ABCMeta

    @classmethod
    def descr(cls):
        """Return a brief description of the module"""
        return ""

    @classmethod
    def options(cls, arggroup):
        """Add options for the module to arggroup.

        arggroup -- an instance of argparse.ArgumentParser"""
        pass


class Source(Node):

    @abstractmethod
    def __iter__(self):
        """Returns an iterator yielding chunks of data as available."""
        return iter([])


class Sink(Node):

    @abstractmethod
    def push(self, chunk):
        """Push a chunk of data to the module for processing.

        Returns True iff the data was of the correct type.

        """
        return False


class RandomAccessSource(Source):
    """Represents a Source that can be accessed using a mapping.

    Classes implementing this interface allow specific chunks to be requested.
    For example:

    for chunk in rsource[1000.0]: do_something

    The supported key types are determined by the implementing class.

    """
    @abstractmethod
    def __getitem__(self, key):
        """Returns an iterator yielding chunks referenced by key"""
        return iter([])


class Filter(Sink, Source):
    pass




