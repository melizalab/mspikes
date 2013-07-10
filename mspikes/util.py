# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 20 17:18:40 2013
"""

def chain_predicates(*ps):
    """Return closure that tests for true returns from all ps. If ps is empty, returns True."""
    return lambda x: all(p(x) for p in ps)


def compose(f1, f2):
    """Return a function that calls f1(f2(*args, **kwargs))"""
    def f(*args, **kwargs):
        return f1(f2(*args, **kwargs))
    return f


def set_option_attributes(obj, opts, **attrs):
    """For each key, value in **attrs, set obj.key = opts.get(key, value)"""
    for key, value in attrs.iteritems():
        setattr(obj, key, opts.get(key, value))


def samples_to_seconds(samples, sampling_rate, offset=None):
    """Convert samples / sampling_rate to canonical form, optionally adding offset"""
    from fractions import Fraction
    val = Fraction(int(samples), int(sampling_rate))
    if offset is not None:
        return offset + val
    else:
        return val

# Variables:
# End:
