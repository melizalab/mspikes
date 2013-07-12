# -*- coding: utf-8 -*-
# -*- mode: python -*-

from nose.tools import *
from nose.plugins.skip import SkipTest

from operator import attrgetter
from mspikes.modules import dispatcher

def test_parallel_wrapper():

    # base class
    class base(object):
        @classmethod
        def options(cls, arg):
            return arg

        def send(self, chunk):
            pass

    wrapped = dispatcher.parallel(attrgetter('id'))(base)

    assert_true(hasattr(wrapped, 'send'))
    assert_true(hasattr(wrapped, 'close'))
    assert_true(hasattr(wrapped, 'throw'))
    assert_equal(wrapped.options(5), base.options(5))
    assert_is_not(wrapped.send, base.send)


def test_parallel_dispatch():
    from mspikes.types import Node, DataBlock
    from mspikes.modules.util import visitor, chain_modules

    counts = []
    chunks = []
    closed = [0]

    # this class counts the number of chunks it gets
    @dispatcher.parallel(attrgetter('id'))
    class counter(Node):
        def __init__(self, count):
            self.count = count

        def send(self, chunk):
            self.count += 1
            counts.append(self.count)
            Node.send(self, chunk)

        def close(self):
            closed[0] += 1

    node = counter(1)
    node.add_target(visitor(chunks.append))

    node.send(DataBlock(id='id_1', offset=0, ds=1, data=(), tags=()))
    node.send(DataBlock(id='id_2', offset=0, ds=1, data=(), tags=()))
    node.send(DataBlock(id='id_2', offset=0, ds=1, data=(), tags=()))
    node.close()

    assert_equal(len(chunks), 3)
    assert_sequence_equal(counts, (2, 2, 3))
    assert_equal(closed[0], 2)


