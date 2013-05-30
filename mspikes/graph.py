# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions for constructing processing graphs.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""
import ast

def parse_node(stmt):
    """Parse a node definition.

    stmt -- an ast node corresponding to a statement in the graphspec

    """
    if not isinstance(stmt, ast.Assign):
        continue
    if not len(stmt.targets) == 1:
        raise SyntaxError("only one node name allowed: %s" % ast.dump(stmt))
    if not isinstance(stmt.value, ast.Call):
        raise SyntaxError("invalid format for node specification: %s" % ast.dump(stmt.value))

    node_name = stmt.targets[0].id
    node_type = stmt.value.func.id

    node_sources = []
    for arg in stmt.value.args:
        if isinstance(arg, (ast.Tuple, ast.List)):
            if not len(arg.elts) == 2:
                raise SyntaxError("source tuple must have two elements: %s" % ast.dump(arg))
            if not isinstance(arg.elts[0], ast.Name):
                raise SyntaxError("first source element must be a symbol: %s" % ast.dump(arg))
            node_sources.append(arg.elts)
        elif isinstance(arg, ast.Name):
            node_sources.apend((arg,))
        else:
            raise SyntaxError("invalid source specification: %s" % ast.dump(arg))

    node_params = dict((k.arg, ast.literal_eval(k.value)) for k in stmt.value.keywords)



def parse_graph(graphspec):
    """Parse an mspikes graph specification.

    The graph specification comprises a list of strings that must have the
    syntax of a python assignment with the form:

    node_name = node_type(*sources, **parameters)

    Sources arguments are only requires for Sink nodes. Each source may be
    - the name of another node
    - a tuple, (node_name, chunk_filter),
      where chunk_filter is either "event" or "sampled"

    Keyword arguments are interpreted as values passed to node_type's
    constructor.

    """

    # parse the tree
    tree = ast.parse(graphspec)
    for stmt in tree.body:
        parse_node(stmt)

    # instantiate the nodes

    # build the graph




# Variables:
# End:
