# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""test mspikes.register

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jun 27 10:47:24 2013
"""
from test.common import *
from mspikes import register
import uuid

ID = 'id1'

def setup():
    register.add_id(ID, prop="value", uuid=None)

@raises(NameError)
def test_add_existing():
    register.add_id(ID)


def test_id_lookup():
    assert_true(register.has_id(ID))


def test_auto_uuid():
    uuid.UUID(register.get_by_id(ID)['uuid'])


def test_key_lookup():
    uu = uuid.uuid4()
    register.add_id('id2', uuid=uu)
    assert_equal(register.id_by_key('uuid', uu), 'id2')
