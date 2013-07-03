# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""mspikes modules for filtering neural data

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul  3 13:22:29 2013
"""
import logging
from mspikes.types import Source, Sink, DataBlock

_log = logging.getLogger(__name__)


class zscale(Source, Sink):
    """Centers and rescales time series data, optionally excluding deviant data

    accepts: time-series data

    emits: z-scaled time-series data
           start and stop exclusions (events)

    """

    pass



# Variables:
# End:
