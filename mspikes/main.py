# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Top-level entry points for mspikes

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:29:44 2013
"""
import inspect
from mspikes import toolchains
from mspikes import graph
from mspikes import modules
from mspikes import filters

def print_descriptions(keyvals, descr):
    """Pretty-print key, descr(value) pairs in keyvals"""
    objs = tuple(keyvals)      # in case it's an iterator
    fmt = "{:<%d}   {}" % max(len(n) for n,_ in objs)
    for n,obj in objs:
        print fmt.format(n, descr(obj))


def print_toolchains():
    """print list of predefined toolchains"""
    from operator import itemgetter
    print_descriptions(inspect.getmembers(toolchains, lambda x : isinstance(x, tuple)), itemgetter(0))


def print_modules():
    """print list of available modules"""
    print "\nmodules:\n========"
    print_descriptions(inspect.getmembers(modules, inspect.isclass), graph.node_descr)


def print_filters():
    """print list of available filters"""
    print "\nfilters:\n========"
    print_descriptions(filters.all(), graph.node_descr)


def print_doc(arg):
    """print full documentation for a toolchain, module, or filter"""
    from inspect import getdoc
    if arg == "":
        print "* To process data in mspikes, pick a predefined toolchain:\n"
        print_toolchains()

        print "\n* Define or extended toolchains with modules and filters:"
        print_modules()
        print_filters()
        print "\n* For more on a toolchain, module, or filter: 'mspikes --doc <entity>'\n"

    elif hasattr(toolchains, arg):
        sdoc,defs = getattr(toolchains, arg)
        print "{}:  {}\n\n{}".format(arg, sdoc, defs)
    elif hasattr(modules, arg):
        doc = getdoc(getattr(modules, arg))
        print "{}:  {}".format(arg, doc)
    elif hasattr(filters, arg):
        doc = getdoc(getattr(filters, arg))
        print "{}:  {}".format(arg, doc)
    else:
        print "E: no such toolchain, module, or filter '{}'".format(arg)


def mspikes(argv=None):
    import argparse
    import logging
    from itertools import chain
    from mspikes import __version__

    p = argparse.ArgumentParser(prog="mspikes",
                                add_help=False,
                                description="Process time-varying data using configurable toolchains")
    p.add_argument("-h", "--help", help="show this message, or options for a toolchain", action='store_true')
    p.add_argument("--doc", help="print extended help information", nargs='?', const="")
    p.add_argument("-v", "--verbose", help="verbose output", action='store_false') # FIXME

    p.add_argument("-t", help="use a predefined toolchain", metavar='NAME', dest="tchain_name")
    p.add_argument("-T", help="define or extend toolchain", action='append', default=[],
                   metavar='DEF', dest="tchain_def")

    opts,args = p.parse_known_args(argv)

    if opts.doc is not None:
        print_doc(opts.doc)
        return 0

    log = logging.getLogger('mspikes')   # root logger
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)-15s [%(name)s] %(message)s")
    if opts.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO
    log.setLevel(loglevel)
    ch.setLevel(loglevel)  # change
    ch.setFormatter(formatter)
    log.addHandler(ch)
    log.info("version %s", __version__)

    # TODO: parse an rc file with user-defined toolchains?
    toolchain = {}
    try:
        if opts.tchain_name:
            toolchain = dict(graph.parse_node_descrs(getattr(toolchains, opts.tchain_name)[1]))
        for expr in opts.tchain_def:
            toolchain.update(graph.parse_node_descrs(expr))

    except AttributeError,e:
        print "E: no such toolchain '{}'".format(opts.tchain_name)
        return -1
    except SyntaxError,e:
        print "E: couldn't parse definition: {}".format(e)
        raise

    # add nodes to the parser so user can set their parameters
    for node_name,node_def in toolchain.iteritems():
        try:
            graph.add_node_to_parser(node_name, node_def, p)
        except AttributeError,e:
            print "E: no such processing module '{}'".format(node_def.type)
            return -1

    if opts.help or len(toolchain)==0:
        p.print_help()
        if len(toolchain) == 0:
            print "\ntoolchains:"
            print_toolchains()
            print ""
        return 0

    opts = p.parse_args(args, opts) # parse remaining args
    try:
        root = graph.build_node_graph(toolchain.items(), opts)
    except AttributeError,e:
        print "E: {}".format(e.message)
        return -1
    except KeyError,e:
        print "E: no such node {}".format(e)
        return -1
    # TODO catch instantiation errors

    # TODO pretty-print the toolchain steps?

    # run the graph
    log.info("starting graph")
    for chunk in chain(*root):
        pass


# Variables:
# End:
