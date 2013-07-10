# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""File input and output nodes that dispatch based on extension

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 11:01:26 2013
"""

from mspikes import types


class file_reader(types.RandomAccessSource):
    pass


class file_writer(types.Sink):
    pass


# Variables:
# End:
