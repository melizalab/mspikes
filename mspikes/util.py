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


def pair_iter(items):
    """For a sequence (p0, p1, p2), yields (p0, p1), (p1, p2), ..."""
    items = iter(items)
    prev = items.next()
    for p in items:
        yield (prev, p)
        prev = p


def set_option_attributes(obj, opts, **attrs):
    """For each key, value in **attrs, set obj.key = opts.get(key, value)"""
    for key, value in attrs.iteritems():
        setattr(obj, key, opts.get(key, value))


def to_seconds(samples, sampling_rate=None, offset=None):
    """Convert samples / sampling_rate to canonical form, optionally adding offset"""
    from fractions import Fraction
    if sampling_rate is None:
        val = float(samples)
    else:
        val = Fraction(int(samples), int(sampling_rate))
    if offset is not None:
        return offset + val
    else:
        return val


def to_samples(seconds, sampling_rate):
    """Convert seconds to integer number of samples, rounding to nearest sample"""
    return long(round(seconds * sampling_rate))

# Variables:
# End:
