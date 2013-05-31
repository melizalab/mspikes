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




