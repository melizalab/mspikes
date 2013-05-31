# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions for constructing processing graphs.

Graphs are composed of Nodes that are either Sources or Sinks. Sources can be
connected to Sinks to form processing graphs. Graphs must have one or more root
Sources, which are linked to Sinks by appending them to the Source.target
property. Graphs may be invoked a blocking mode through iteration on the root
Source(s). Each iteration will only complete once all the dependent nodes have
received and processed the data chunk.

For example:

reader = generic_file_reader(filename, ...)
filter = generic_filter(...)
writer = generic_file_writer(filename, ...)

reader.targets.append(filter)
filter.targets.append(writer)

for t in reader:
    update_status_display(t)


Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""
import ast
from collections import namedtuple

# representation of node definition
_node_def = namedtuple("_node_def",("name","type","sources","params"))


def get_node_type(node_type_name):
    """Look up a node class by name"""
    import mspikes.modules
    # TODO scan entry points
    return getattr(mspikes.modules, node_type_name)


def get_data_filter(data_filter_name):
    """Look up a data filter function by name"""
    import mspikes.data_filters
    # TODO scan entry points
    return getattr(mspikes.data_filters, data_filter_name)


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
        raise SyntaxError("only one assignment allowed: %s" % ast.dump(stmt))
    if not isinstance(stmt.targets[0], ast.Name):
        raise SyntaxError("only one assignment allowed: %s" % ast.dump(stmt))
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
            node_sources.append((arg.id,None))
        else:
            raise SyntaxError("invalid source specification: %s" % ast.dump(arg))

    return _node_def(name=stmt.targets[0].id,
                     type=stmt.value.func.id,
                     sources=tuple(node_sources),
                     params=dict((k.arg, ast.literal_eval(k.value)) for k in stmt.value.keywords))


def add_node_to_parser(node_def, parser):
    """Add a group to an argparse.ArgumentParser for setting options of nodes"""
    cls = get_node_type(node_def.type)
    group = parser.add_argument_group(node_def.name, cls.descr())
    cls.options(group, node_def.name)


# class node_graph(object):
#     """Represents a processing graph.
#     """

#     def __init__(self,):
#         self._nodes = {}        # nodes by name
#         self._head = []         # nodes with no source

#     def add_node(self, node):
#         """Add a node to the tree.

#         node -- a node definition, with attributes ("name", "type") and
#                 optional ("sources", "params"). The node defined by this
#                 argument will be instantiated and linked to its parent nodes.

#         raises KeyError if the parent node doesn't exist

#         """
#         # look up type by name

#         # instantiate
#         params = getattr(node, "params", dict())
#         obj = cls(**params)
#         self._nodes[node.name] = obj

#         if hasattr(node, "sources") and node.sources is not None:
#             for source, filt in node.sources:
#                 # look up filter function
#                 parent = self._nodes[source]
#                 if not hasattr(parent, "targets"):
#                     parent.targets = []
#                 parent.targets.append((obj, filt))
#         else:
#             self._head.append(obj)


# Variables:
# End:
