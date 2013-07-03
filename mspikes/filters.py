# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Functions to filter data chunks. Filtering can be by tag or with a function.

Copyright (C) 2013 Dan Meliza <dmeliza@uchicago.edu>
Created Fri May 31 13:19:05 2013

"""

def get(name):
    """Look up filter in this module.

    If 'name' starts with '_', it's interpreted as a tag lookup; otherwise, it's taken
    to refer to a function in this module or one registered with the
    org.meliza.mspikes.filters entry point.

    """
    if name.startswith('_') and len(name) > 1:
        tag = name[1:]
        def f(obj):
            return (tag in obj.tags)
        f.__name__ = name
        return f
    else:
        filts = dict(all())
        try:
            return filts[name]
        except KeyError:
            raise AttributeError("no such filter '%s'" % name)

def all():
    import inspect
    return inspect.getmembers(inspect.getmodule(all),
                              lambda x: inspect.isfunction(x) and x.__name__ not in ('get','all'))

# Variables:
# End:
