# -*- coding: utf-8 -*-
# -*- mode: python -*-

from nose.tools import *
from nose.plugins.skip import SkipTest

from mspikes import graph

def test_node_syntax():

    n = graph.parse_node("node_name = node_type()")
    assert n.name == "node_name"
    assert n.type == "node_type"
    assert len(n.sources) == 0
    assert len(n.params) == 0

    n = graph.parse_node("node_name = node_type(source1, (source2, events), param1=1234)")
    assert n.name == "node_name"
    assert n.type == "node_type"
    assert_sequence_equal(n.sources, (("source1",), ("source2","events")))
    assert_dict_equal(n.params, {"param1" : 1234 })

# TODO check some basic syntax errors
