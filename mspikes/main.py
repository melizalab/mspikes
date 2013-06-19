# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Top-level entry points for mspikes

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:29:44 2013
"""
import ast
from mspikes import toolchains
from mspikes import graph


def print_toolchains():
    """print list of predefined toolchains"""
    names = [n for n in dir(toolchains) if not n.startswith("__")]
    fmt = "{:<%d}   {}" % max(map(len, names))

    for n in names:
        print fmt.format(n, getattr(toolchains, n)[0])


def parse_toolchain_defn(defn):
    """parse toolchain definition"""
    return tuple(graph.parse_node(d) for d in ast.parse(defn).body)


def mspikes(argv=None):
    import argparse

    p = argparse.ArgumentParser(prog="mspikes",
                                add_help=False,
                                description="Process time-varying data.")
    p.add_argument("-h","--help", help="show this message, or options for a toolchain", action='store_true')

    p.add_argument("-t", help="use a predefined toolchain", metavar='NAME', dest="tchain_name")
    p.add_argument("-T", help="define or extend toolchain", action='append', default=[],
                   metavar='DEF', dest="tchain_def")

    opts,args = p.parse_known_args(argv)
    print opts

    # TODO: parse an rc file with user-defined toolchains?
    toolchain = []
    try:
        if opts.tchain_name:
            toolchain = graph.parse_graph_descr(getattr(toolchains, opts.tchain_name)[1])
        for expr in opts.tchain_def:
            toolchain.extend(graph.parse_graph_descr(expr))

    except AttributeError,e:
        print "E: no such toolchain {}".format(opts.tchain_name)
        raise
    except SyntaxError,e:
        print "E: couldn't parse definition: {}".format(e)
        raise

    for node_def in toolchain:
        graph.add_node_to_parser(node_def, p)

    # TODO pretty-print toolchain

    if opts.help or len(args)==0:
        p.print_help()
        if len(toolchain) == 0:
            print "\npredefined toolchains:"
            print_toolchains()

# Variables:
# End:
