# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Top-level register for data chunk ids

Data sources should register chunk ids as follows:

add_id(id, **properties)

Check whether an id already exists:

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
"""
import logging

_register = {}
_log = logging.getLogger('mspikes.register')


def add_id(id, **properties):
    """Add an identity to the register. Raises a NameError if the id has already been registered"""
    if has_id(id):
        raise NameError("'%s' has already been registered" % id)
    _register[id] = properties
    _log.debug("'%s' properties: %s", id, properties)


def has_id(id):
    """Return true if id has been registered"""
    return id in _register


def get_properties(id):
    """Return properties for id. If id has not been registered, returns an empty dict"""
    try:
        return _register[id]
    except KeyError:
        return {}
