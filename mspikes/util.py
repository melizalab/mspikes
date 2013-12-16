# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Utility functions

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 20 17:18:40 2013
"""
from collections import defaultdict


def chain_predicates(*ps):
    """Return closure that tests for true returns from all ps. If ps is empty, returns True."""
    return lambda x: all(p(x) for p in ps)


def any_regex(*regexes):
    """Return closure that tests for match against any of the arguments"""
    import re
    rx = [re.compile(regex).match for regex in regexes]
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
    return long(round(seconds * float(sampling_rate)))


def natsorted(key):
    """ key function for natural sorting. usage: sorted(seq, key=natsorted) """
    import re
    return map(lambda t: int(t) if t.isdigit() else t, re.split(r"([0-9]+)",key))


def cutarray(x, cuts):
    """Cut array x into subarrays defined by the upper exclusive boundaries in cuts.

    Returns a generator that yields (upper_bound, sub_array) tuples for each
    element in cuts that corresponds to a non-empty array, followed by (None,
    subarray) for all elements in x greater than the final element in cuts.

    Preconditions: both arguments must be sorted

    """
    from bisect import bisect_left
    pos = 0
    for i, cut in enumerate(cuts):
        idx = bisect_left(x, cut, pos)
        if idx > pos:
            yield (cut, x[pos:idx])
            pos = idx
    if pos < len(x):
        yield (None, x[pos:])


class defaultdict(defaultdict):

    def __missing__(self, key):
        """override for defaultdict.__missing__ that calls default_factory with a key """
        try:
            f = self.default_factory
        except AttributeError:
            raise KeyError(key)
        self[key] = f(key)
        return self[key]


# Variables:
# End:
