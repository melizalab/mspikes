# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions for constructing processing graphs.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Wed May 29 15:44:00 2013

"""

def node_regex():
    """Returns a regular expression for parsing node specifications"""
    import re
    symbol = r"[a-zA-Z_]\w*"
    value = r"\w+"
    str_value = r'".*?"'
    return re.compile(r"^" symbol r"\s+" symbol)



def parse_graph(graphspec):
    """Parse an mspikes graph specification.

    The graph specification comprises a list of strings that must match the
    following regular expression.

    node = node-name SP node-spec
    node-spec = node-type *node-arg
    node-arg  = SP (node-keyword SP node-value) / (node-value)
    node-value = numeric-value / string-value
    node-name = symbol
    node-type = symbol
    node-keyword = %x3A symbol  ; lisp-style keyword
    symbol = ALPHA *(ALPHA / DIGIT / %x5F )
    numeric-value

    """

# Variables:
# End:
