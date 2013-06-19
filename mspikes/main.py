# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Top-level entry points for mspikes

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:29:44 2013
"""
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
    import ast
    return tuple(graph.parse_node(d) for d in ast.parse(defn).body)


def mspikes(argv=None):
    import argparse

    p = argparse.ArgumentParser(prog="mspikes",
                                add_help=False,
                                description="Process time-varying data.")
    p.add_argument("-h","--help", help="show this message, or options for a toolchain", action='store_true')
    p.add_argument("--toolchain-help", help="show help on defining toolchains", action='store_true')

    g = p.add_mutually_exclusive_group()
    g.add_argument("-t", help="use a predefined toolchain", metavar='NAME', dest="tchain_name")
    g.add_argument("-T", help="define a toolchain", metavar='DEF', dest="tchain_def")

    args = p.parse_args(argv)
    print args

    try:
        if args.tchain_name:
            defn = getattr(toolchains, args.tchain_name)[1]
        elif args.tchain_def:
            defn = args.tchain_def
        else:
            defn = None
        toolchain = defn and parse_toolchain_defn(defn)
        for node_def in toolchain:
            graph.add_node_to_parser(node_def, p)

    except AttributeError,e:
        print "E: no such toolchain {}".format(args.tchain_name)
        raise
    except SyntaxError,e:
        print "E: couldn't parse definition: {}".format(e)
        raise

    if args.help:
        if toolchain is None:
            p.print_help()
            print "\npredefined toolchains:"
            print_toolchains()
        else:
            pass

# Variables:
# End:
