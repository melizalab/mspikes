# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions for constructing processing graphs.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""
from collections import namedtuple
import ast

# representation of node definition
_node_def = namedtuple("_node_def",("name","type","sources","params"))

def parse_node(stmt):
    """Parse a node definition.

    stmt -- either a string, which will parsed with Python's ast module, or an
            already parsed ast.Assign object.

    returns a tuple (node_name, node_type, sources, parameters), with symbol
    names represented as strings (i.e. the classes are not instantiated)

    Nodes are defined with the following syntax:

    node_name = node_type(*sources, **parameters)

    node_name must be a valid python identifier

    node_type must be the name of a python class in the mspikes.modules module.
    Additional classes may be registered with the 'org.meliza.mspikes.modules'
    entry point using setuptools.

    *sources signifies zero or more sources, separated by commas. Each source
     must be the name of another node, or a tuple (node_name, chunk_filter),
     where chunk_filter must be the name of a function in the mspikes.filters
     module. Additional callables may be registered with the
     'org.meliza.mspikes.filters' entry point.

    **parameters signifies zero or more key=value pairs, separated by commas.
      These are passed as keyword arguments to the node_type constructor.

    raises SyntaxError for failures to conform to the above syntax

    """

    if isinstance(stmt, basestring):
        stmt = ast.parse(stmt, "single").body[0]

    if not isinstance(stmt, ast.Assign):
        raise SyntaxError("definition is not an assignment: %s" % ast.dump(stmt))
    if not len(stmt.targets) == 1:
        raise SyntaxError("only one node name allowed: %s" % ast.dump(stmt))
    if not isinstance(stmt.value, ast.Call):
        raise SyntaxError("invalid format for node specification: %s" % ast.dump(stmt.value))

    node_sources = []
    for arg in stmt.value.args:
        if isinstance(arg, (ast.Tuple, ast.List)):
            if not len(arg.elts) == 2:
                raise SyntaxError("source tuple must have two elements: %s" % ast.dump(arg))
            if not all(isinstance(a, ast.Name) for a in arg.elts):
                raise SyntaxError("source tuple elements must be symbol names: %s" % ast.dump(arg))
            node_sources.append(tuple(a.id for a in arg.elts))
        elif isinstance(arg, ast.Name):
            node_sources.append((arg.id,))
        else:
            raise SyntaxError("invalid source specification: %s" % ast.dump(arg))

    return _node_def(name=stmt.targets[0].id,
                     type=stmt.value.func.id,
                     sources=node_sources,
                     params=dict((k.arg, ast.literal_eval(k.value)) for k in stmt.value.keywords))


# def parse_graph(graphspec):
#     """Parse an mspikes graph specification.

#     The graph specification comprises a list of strings that must have the
#     syntax of a python assignment with the form:


#     Sources arguments are only requires for Sink nodes. Each source may be

#     Keyword arguments are interpreted as values passed to node_type's
#     constructor.

#     """

#     # parse the tree
#     tree = ast.parse(graphspec)
#     for stmt in tree.body:
#         parse_node(stmt)

#     # instantiate the nodes

#     # build the graph


class node_graph(object):
    """Represents a processing graph.
    """

    def __init__(self,):
        self._nodes = {}        # nodes by name
        self._head = []         # nodes with no source

    def add_node(self, node):
        """Add a node to the tree.

        node -- a node definition, with attributes ("name", "type") and
                optionall ("sources", "params"). The node defined by this
                argument will be instantiated and linked to its parent nodes.

        raises ValueError if the parent node doesn't exist

        """

        # look up type by name

        # instantiate
        params = getattr(node, "params", dict())
        obj = cls(**params)
        self._nodes[node.name] = obj

        if hasattr(node, "sources") and node.sources is not None:
            # check parents
            pass
        else:
            self._head.append(obj)


# Variables:
# End:
