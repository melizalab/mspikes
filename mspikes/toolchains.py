# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Predefined toolchains.

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:55:10 2013
"""

spk_extract = ("Extract spikes from raw neural recordings",
                 "input = file_reader(); "
                 "hpass = highpass_filter((input, sampled)); "
                 "spikes = spike_detect(hpass); "
                 "output = file_writer(spikes)")


# Variables:
# End:
