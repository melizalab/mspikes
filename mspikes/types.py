# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Basic types and concepts for mspikes.

"""
from collections import namedtuple

# simple immutable struct for transporting blocks of data
DataBlock = namedtuple("DataBlock", ("id", "offset", "ds", "data", "tags"))


def tag_set(*args):
    """return a set of tags"""
    return frozenset(intern(s) for s in args)


class Node(object):
    """A node in a processing graph."""

    @classmethod
    def options(cls, argfun, **defaults):
        """Add options for the Node to arggroup.

        argfun -- a closure with the same signature as
                  ArgumentParser.add_argument

        Additional keyword arguments contain parameters set in the node
        definition.

        """
        pass

    def add_target(self, target, filter=None):
        """Tell the Node to send data to target

        target  -- an object with a send() method

        filter -- an optional predicate function that must return True for the
        data to be sent to target

        """
        if not hasattr(self, "_targets"): self._targets = []
        self._targets.append((target, filter))

    def send(self, data):
        """Send a chunk of data to the node.

        Default behavior is to broadcast the chunk to all connected targets
        (after filtering).

        """
        from mspikes import DEBUG

        if not hasattr(self, "_targets"):
            return
        if not DEBUG and "debug" in data.tags:
            return
        for tgt, filt in self._targets:
            if filt is None or filt(data): tgt.send(data)

    def done(self):
        """Called by upstream Sources when data stream is exhausted.

        This method provides a mechanism for processing modules to indicate
        whether they've finished processing, or whether an additional pass is
        neeeded. If the node is still processing data, it should block until
        it's done. If the node has processed all the data, but needs another
        pass, it should return False. If the node is terminal (has no sinks),
        and is completely finished, it should return True. If the node is not
        terminal, it should return all(x.done() for x in self._targets)

        """
        pass


class Source(Node):
    """A Node that produces data."""

    def send(self, data):
        raise NotImplementedError("Don't call send on Sources, but instead iterate over them")

    def __iter__(self):
        """Process chunks of data and push them to connected targets

        Yields the generated chunks.

        Note: call done() after the iterator exits to join running threads and
        determine whether an additional pass is needed.

        """
        pass


class RandomAccessSource(Source):
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
        pass


# Variables:
# End:
