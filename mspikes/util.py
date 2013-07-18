# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 20 17:18:40 2013
"""

def chain_predicates(*ps):
    """Return closure that tests for true returns from all ps. If ps is empty, returns True."""
    return lambda x: all(p(x) for p in ps)

def any_regex(*regexes):
    """Return closure that tests for match against any of the arguments"""
    import re
    rx = [re.compile(regex).search for regex in regexes]
    def multimatch(x):
        return any(p(x) for p in rx)
    multimatch.__doc__ = " | ".join(regexes)
    return multimatch


def compose(f1, f2, unpack=False):
    """Return a function that calls f1(f2(*args, **kwargs))"""
    assert callable(f1)
    assert callable(f2)

    if unpack:
        def composition(*args, **kwargs):
            return f1(*f2(*args, **kwargs))
    else:
        def composition(*args, **kwargs):
            return f1(f2(*args, **kwargs))
    return composition


def pair_iter(items):
    """For a sequence (p0, p1, p2), yields (p0, p1), (p1, p2), ..."""
    items = iter(items)
    prev = items.next()
    for p in items:
        yield (prev, p)
        prev = p


def repeatedly(func, *args, **kwargs):
    """Iterate over return values from calling func(*args, **kwargs) repeatedly.

    Continues until func throws an exception.

    Example:
    >>> arr = [1,2,3]
    >>> [x for x in repeatedly(arr.pop, 0)]
    [1, 2, 3]
    >>> arr
    []

    """
    try:
        while True:
            yield func(*args, **kwargs)
    except:
        raise StopIteration


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
