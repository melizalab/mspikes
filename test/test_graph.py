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
test_defs = [("node1 = node_type()", "node1", ("node_type",(),{})),
             ("node2 = node_type(param1=1234)", "node2", ("node_type",(),{"param1":1234})),
             ("node3 = node_type(node1, (node2, events))", "node3",
              ("node_type", (("node1",),("node2","events")), {}))
         ]

bad_defs = ["not an assignment",
            "node1 = not_a_call",
            "node1,node2 = too_many_lhs()",
            "node3 = bad_python_syntax(blah, param1="]


def parse_node(statement, *result):
    name,node = graph.parse_node_descr(statement)
    assert_equal(name, result[0])
    assert_sequence_equal(node, result[1])


def test_node_syntax():
    for statement, name, node in test_defs:
        yield parse_node, statement, name, node

    f = raises(SyntaxError)(parse_node)
    for statement in bad_defs:
        yield f, statement, None


# test lookup and doc generation for all nodes
node_types = inspect.getmembers(modules, inspect.isclass)

def test_chain_doc():
    """ test construction of argparser with node docs """
    import argparse

    parser = argparse.ArgumentParser("test", add_help=False)
    code = ";".join("node{} = {}()".format(i,n) for i,(n,t) in enumerate(node_types))
    for name,node_def in graph.parse_node_descrs(code):
        graph.add_node_to_parser(name, node_def, parser)

    parser.print_help()


# test graph creation and running
toolchains = [("rng = rand_samples(seed=10)",
               "out = stream_sink((rng,sampled))")]


def create_graph(definitions):
    node_defs = graph.parse_node_descrs(";".join(definitions))
    node_graph = graph.build_node_graph(node_defs)

    assert len(node_graph) == sum(1 for _,d in node_defs if len(d.sources))
    return node_graph


def run_graph(graph):
    from itertools import chain
    for x in chain(*graph):
        pass


def test_graph_run():
    for defs in toolchains:
        chain = create_graph(defs)
        #yield run_graph, chain
