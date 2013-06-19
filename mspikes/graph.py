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

reader = generic_file_reader(filename, ...)
filter = generic_filter(...)
writer = generic_file_writer(filename, ...)

reader.targets.append(filter)
filter.targets.append(writer)

for t in reader:
    update_status_display(t)

Graphs can be constructed programmatically or by parsing a set of definitions.
The definitions have a python-based syntax (see parse_node). Building a graph is
accomplished in several passes:

Pass 1: parse_node_descr() converts python statements to abstract node definitions
Pass 2: instantiate nodes and filters
Pass 3: link target nodes to sources

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""
import ast
from collections import namedtuple

# representation of node definition
NodeDef = namedtuple("NodeDef", ("name", "type", "sources", "params"))


def parse_node_descr(expr):
    """Parse a node description.

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
            node_sources.append((arg.id, None))
        else:
            raise SyntaxError("invalid source specification: %s" % ast.dump(arg))

    return NodeDef(name=expr.targets[0].id,
                   type=expr.value.func.id,
                   sources=tuple(node_sources),
                   params=dict((k.arg, ast.literal_eval(k.value)) for k in expr.value.keywords))


def parse_graph_descr(code):
    """Parse a node graph description.

    code -- a string, to be parsed with Python's ast module

    returns a tuple of NodeDef objects

    """
    if isinstance(code, basestring):
        exprs = ast.parse(code, "single").body
    elif isinstance(code, ast.Module):
        exprs = code.body
    elif isinstance(code, ast.Assign):
        exprs = (code,)

    return tuple(parse_node_descr(expr) for expr in exprs)


def resolve_symbol(name, namespace, entry_point=None):
    """Look up an object by name"""
    # TODO scan entry points
    # TODO throw more useful error type
    return getattr(namespace, name)


def add_node_to_parser(node_def, parser):
    """Add a group to an argparse.ArgumentParser for setting options of nodes"""
    from mspikes import modules
    cls = resolve_symbol(node_def.type, modules)
    group = parser.add_argument_group(node_def.name, cls.descr())
    cls.options(group, node_def.name, **node_def.params)


def build_node_graph(node_defs, **options):
    """Instantiate nodes and assemble into a graph

    node_defs -- sequence of node definitions (as returned by parse_node())

    options -- mapping with qualified construction parameters (e.g.
               nodename_paramname) as keys

    Returns a list of the head nodes (i.e., leaf Sources) in the graph, with
    downstream nodes linked.

    """
    import itertools
    from mspikes import modules, filters

    # instantiate the nodes
    nodes = dict()
    sources = dict()
    for n in node_defs:
        cls = resolve_symbol(n.type, modules)
        opts = dict((k[len(n.name)+1:],v) for k,v in options.iteritems() if k.startswith(n.name))
        nodes[n.name] = cls(**opts)
        if len(n.sources) > 0: sources[n.name] = n.sources

    # assemble the graph
    head = []
    for name,node in nodes.iteritems():
        if name not in sources:
            head.append(node)
            continue

        for source in sources[name]:
            if source[0] not in nodes:
                raise NameError("{} attempts to reference non-existent node {}".format(name, source[0]))
            src_filts = tuple(resolve_symbol(x, filters) for x in source[1:])
            nodes[source[0]].targets.append((node, src_filts))

    return head



# Variables:
# End:
