# -*- coding: utf-8 -*-
# -*- mode: python -*-

from nose.tools import *
from nose.plugins.skip import SkipTest

import inspect

from mspikes import graph
from mspikes import modules


def test_argparse_prefixer():
    import argparse
    pfx = "prx"
    keys = ("--badger","bacon")
    parser = argparse.ArgumentParser()

    fn = graph.argparse_prefixer(pfx, parser)
    assert_equal(fn("-b",default="").dest, 'b')
    for k in keys: fn(k, default="")

    n = parser.parse_args(["blah"])
    assert_set_equal(set(graph.argparse_extracter(n, pfx).keys()),
                     set(k.replace('-','') for k in keys))

# test syntax of graph parser
def parse_node_descr(statement, *result):
    name,node = graph.parse_node_descr(statement)
    assert_equal(name, result[0])
    assert_sequence_equal(node, result[1])


def test_node_syntax():
    test_defs = [("node1 = node_type()", "node1", ("node_type",(),{})),
                 ("node2 = node_type(param1=1234)", "node2", ("node_type",(),{"param1":1234})),
                 ("node3 = node_type(node1, (node2, events))", "node3",
                  ("node_type", (("node1",),("node2","events")), {})),
                 ("node4 = node_type((node1, _sampled))", "node4",
                  ("node_type", (("node1","_sampled"),), {})),
             ]
    for statement, name, node in test_defs:
        yield parse_node_descr, statement, name, node

        bad_defs = ["not an assignment",
                    "node1 = not_a_call",
                    "node1,node2 = too_many_lhs()",
                    "node3 = bad_python_syntax(blah, param1=",
                    "node5 = node_type((node1, has_all(_sampled))))", # not yet
                ]
    f = raises(SyntaxError)(parse_node_descr)
    for statement in bad_defs:
        yield f, statement, None


# test lookup and doc generation for all nodes
def test_chain_doc():
    """ test construction of argparser with node docs """
    import argparse

    node_types = inspect.getmembers(modules, inspect.isclass)
    parser = argparse.ArgumentParser("test", add_help=False)
    code = ";".join("node{} = {}()".format(i,n) for i,(n,t) in enumerate(node_types))
    for name,node_def in graph.parse_node_descrs(code):
        graph.add_node_to_parser(name, node_def, parser)

    parser.print_help()


# test graph creation and running


def create_graph(definitions):
    node_defs = graph.parse_node_descrs(";".join(definitions))
    node_graph = graph.build_node_graph(node_defs)

    assert_equal(len(node_graph), sum(1 for _,d in node_defs if len(d.sources)))


def test_graph_run():
    toolchains = [("rng = rand_samples(seed=10)",
                   "out = stream_sink((rng, _sampled))")]

    for descrs in toolchains:
        yield create_graph, descrs
