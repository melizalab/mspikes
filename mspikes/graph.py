# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions for constructing processing graphs.

Graphs are composed of Nodes that are either Sources or Sinks. Sources can be
connected to Sinks to form processing graphs. Graphs must have one or more root
Sources, which are linked to Sinks by appending them to the Source.target
property. Graphs may be invoked in a blocking mode through iteration on the root
Source(s). Each iteration will only complete once all the dependent nodes have
received and processed the data chunk.

For example:

input = generic_file_reader(filename, ...)
trans = generic_transform(...)
output = generic_file_writer(filename, ...)

input.add_sink(trans)
filter.targets.append(writer)

for t in reader:
    update_status_display(t)

Graphs can be constructed programmatically or by parsing a set of definitions.
The definitions have a python-based syntax (see parse_node). Building a graph is
accomplished in several passes:

Pass 1: generate node definitions from python expressions
Pass 2: instantiate node objects from node definitions
Pass 3: build graph by linking target node objects to source
        node objects (looking up filters)

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""
import ast
from collections import namedtuple

# representation of node definition
NodeDef = namedtuple("NodeDef", ("type", "sources", "params"))


def parse_node_descr(expr):
    """Parse a node description. Returns (name,NodeDef).

    Nodes are defined with the following python-based syntax:

    node_name = node_type(*sources, **parameters)

    node_name must be a valid python identifier

    node_type must be the name of a python class in the mspikes.modules
    namespace. Additional classes may be registered with the
    'org.meliza.mspikes.modules' entry point using setuptools.

    *sources signifies zero or more sources, separated by commas. Each source
     must be the name of another node, or a tuple
     (node_name,filter,[filter],...), where filter must be the name of a
     function in the mspikes.filters namespace. Filters are applied in sequence.
     Additional callables may be registered with the
     'org.meliza.mspikes.filters' entry point.

    **parameters signifies zero or more key=value pairs, separated by commas.
      These are passed as keyword arguments to the node_type constructor.

    raises SyntaxError for failures to conform to the above syntax

    """
    if isinstance(expr, basestring):
        expr = ast.parse(expr, "single").body[0]

    if not isinstance(expr, ast.Assign):
        raise SyntaxError("expression is not an assignment")
    if not  isinstance(expr.value, ast.Call):
        raise SyntaxError("left side of expression not a call()")
    if not len(expr.targets) == 1 or not isinstance(expr.targets[0], ast.Name):
        raise SyntaxError("right side of expression not single symbol")

    node_sources = []
    for arg in expr.value.args:
        if isinstance(arg, (ast.Tuple, ast.List)):
            if not all(isinstance(a, ast.Name) for a in arg.elts):
                raise SyntaxError("source tuple elements must be symbol names: %s" % ast.dump(arg))
            node_sources.append(tuple(a.id for a in arg.elts))
        elif isinstance(arg, ast.Name):
            node_sources.append((arg.id,))
        else:
            raise SyntaxError("invalid source specification: %s" % ast.dump(arg))

    return (expr.targets[0].id,
            NodeDef(type=expr.value.func.id,
                    sources=tuple(node_sources),
                    params=dict((k.arg, ast.literal_eval(k.value)) for k in expr.value.keywords)))


def parse_node_descrs(code):
    """Parse a node graph description, with one or more node definitions.

    code -- a string, to be parsed with Python's ast module

    returns a tuple of (name, NodeDef) tuples

    """
    if isinstance(code, basestring):
        exprs = ast.parse(code, "single").body
    elif isinstance(code, ast.Module):
        exprs = code.body
    elif isinstance(code, ast.Assign):
        exprs = (code,)

    return tuple(parse_node_descr(expr) for expr in exprs)


def node_descr(cls):
    """Get node description from docstr"""
    from inspect import getdoc
    return getdoc(cls).split("\n")[0]


def argparse_prefixer(prefix, group):
    """Returns closure for adding prefixed options to an argparser"""
    import re
    rx = re.compile(r"^(--|)(\w)")
    def f(*args, **kwargs):
        # adds prefix to options
        args = map(lambda x : rx.sub(r"\1%s-\2" % prefix, x), args)
        # TODO add default to help text
        return group.add_argument(*args, **kwargs)
    return f


def argparse_extracter(namespace, prefix):
    """Returns a dict of the attributes in namespace starting with prefix.

    Reverses the operation of argparse_prefixer
    """
    from itertools import imap, izip
    import re
    if namespace is None:
        return dict()
    rx = re.compile(r"^%s(?:-|_)(.*)" % prefix)
    keys = dir(namespace)
    return dict((m.group(1),getattr(namespace,s))
                for m,s in izip(imap(rx.match, keys), keys) if m)


def add_node_to_parser(name, node_def, parser):
    """Add a group to an argparse.ArgumentParser for setting options of """
    from mspikes import modules
    cls = getattr(modules, node_def.type)
    group = parser.add_argument_group(name, node_descr(cls))
    cls.options(argparse_prefixer(name, group), **node_def.params)
    return group


def chain_predicates(*ps):
    """Return closure that tests for true returns from all ps. If ps is empty, returns True."""
    return lambda x: all(p(x) for p in ps)


def build_node_graph(node_defs, options=None):
    """Instantiate nodes and assemble into a graph

    node_defs -- sequence of tuples, (name, node_def)

    options -- construction parameters for nodes; attributes are matched
               with nodes using names; pattern is nodename_paramname

    Returns a list of the head nodes (i.e., leaf Sources) in the graph, with
    downstream nodes linked.

    """
    from itertools import imap, starmap
    from mspikes import modules, filters

    # instantiate the nodes (pass 2)
    nodes = dict((name, getattr(modules,node_def.type)(**argparse_extracter(options, name)))
                  for name,node_def in node_defs)

    def reslv(src,*filts):
        from functools import partial
        return nodes[src], tuple(imap(partial(getattr, filters), filts))

    # assemble the graph (pass 3)
    head = []
    for name,node_def in node_defs:
        node = nodes[name]
        for source,filts in starmap(reslv, node_def.sources):
            # source.add_sink(node, filts)
            # compose filters into a single function
            source.add_sink(node, chain_predicates(*filts))
        if len(node_def.sources) == 0:
            head.append(node)

    return head



# Variables:
# End:
