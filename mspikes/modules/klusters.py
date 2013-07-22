# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""klusters format import and export

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jul 18 17:08:57 2013
"""

import logging
from mspikes import util
from mspikes.types import DataBlock, Node, Source, tag_set, MspikesError


class KlustersError(MspikesError):
    """Raised for errors reading or writing klusters data"""
    pass


class export_klusters(Node):
    """Export spike times and waveforms to klusters/klustakwik format

    accepts:  _events (marked point process, start=time, spike=waveform)
    emits:    none

    Outputs a number of files that can be used with Klusters or KlustaKwik.
     <basename>.spk.<g> - the spike file
     <basename>.fet.<g> - the feature file
     <basename>.clu.<g> - the cluster file (all spikes assigned to one cluster)
     <basename>.xml - the control file used by Klusters

    """
    _log = logging.getLogger("%s.spike_extract" % __name__)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("basename",
                 help="base name for output files (warning: overwrites existing files)",)
        addopt_f("--kkwik",
                 help="run KlustaKwik after writing files",
                 action='store_true')

    def __init__(self, basename, **options):
        util.set_option_attributes(self, options, kkwik=False)


    def send(self, chunk):
        """ write to clu/spk/fet files"""
        data = chunk.data
        if "events" not in chunk.tags or data.dtype.names is None or "spike" not in data.dtype.names:
            return




    def close(self):
        """ write xml file """
        pass

class import_klusters(Source):
    """Import spike clusters from klusters format"""

    pass


# Variables:
# End:
