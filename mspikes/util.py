# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 20 17:18:40 2013
"""

def chain_predicates(*ps):
    """Return closure that tests for true returns from all ps. If ps is empty, returns True."""
    return lambda x: all(p(x) for p in ps)


# Variables:
# End:
