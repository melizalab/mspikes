#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Module with some utility functions and classes for mspikes

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
from collections import defaultdict

class defaultdict(defaultdict):
    """
    Improved defaultdict that passes key value to __missing__

    Example:
    >>> def lfactory(x): return [x]
    >>> dd = defaultdict(lfactory)
    >>> dd[1]
    [1]

    Makes a good handler of file objects.
    """
    def __missing__(self, key):
        if self.default_factory is None: raise KeyError((key,))
        self[key] = value = self.default_factory(key)
        return value


# Variables:
# End:
