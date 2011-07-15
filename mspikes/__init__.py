# -*- coding: iso-8859-1 -*-
"""
mspikes extracts spike times and waveforms from extracellular data
stored in ARF files.  The main entry points are in spike_extract,
which does the thresholding, realignment, and PCA calculations, and in
group_events, which generates toe_lis files with trials grouped by
unit and stimulus.

Component modules
===============================
extractor   functions for detecting and processing spike events
klusters    read and write klusters/klustakwik file formats
spikes      extension module with signal processing and spike extraction code

"""
from extractor import __version__
__all__ = ['extractor','klusters']

# Variables:
# End:
