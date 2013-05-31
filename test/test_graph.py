# -*- coding: utf-8 -*-
# -*- mode: python -*-

from nose.tools import *
from nose.plugins.skip import SkipTest

import inspect

from mspikes import graph
from mspikes import modules

# get some modules to play with
node_types = inspect.getmembers(modules, inspect.isclass)

test_defs = [("node1 = node_type()", ("node1","node_type",(),{})),
             ("node2 = node_type(param1=1234)", ("node2","node_type",(),{"param1":1234})),
             ("node3 = node_type(node1, (node2, events))", ("node3","node_type",
                                                            (("node1",None),("node2","events")),
                                                            {}))
         ]

bad_defs = ["not an assignment",
            "node1 = not_a_call",
            "node1,node2 = too_many_lhs()",
            "node3 = bad_python_syntax(blah, param1="]

def parse_node(statement, result):
    n = graph.parse_node(statement)
    assert_sequence_equal(n, result)


def test_node_syntax():
    for statement, result in test_defs:
        yield parse_node, statement, result

    f = raises(SyntaxError)(parse_node)
    for statement in bad_defs:
        yield f, statement, None


def test_node_lookup():
    for name, type in node_types:
        assert graph.get_node_type(name) == type


def test_chain_doc():
    """ test that an argparser can be constructed """
    import argparse

    parser = argparse.ArgumentParser("test", add_help=False)

    for i,(n,t) in enumerate(node_types):
        node_str = "node{} = {}()".format(i,n)
        node_def = graph.parse_node(node_str)
        graph.add_node_to_parser(node_def, parser)

    parser.print_help()

toolchains = [("rng = random_samples(seed=10)",
               "out = stream_sink((rng,sampled))")]

def create_graph(definitions):
    node_defs = [graph.parse_node(d) for d in definitions]
    node_graph = graph.build_node_graph(node_defs)

    assert len(node_graph) == sum(1 for d in node_defs if len(d.sources))
    return node_graph

def run_graph(graph):
    from itertools import chain
    for x in chain(*graph):
        pass

def test_graph_creation():
    for defs in toolchains:
        yield create_graph, defs

def test_graph_run():
    for defs in toolchains:
        chain = create_graph(defs)
        yield run_graph, chain
