# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Predefined toolchains.

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:55:10 2013
"""

view_raw = ("Inspect raw sampled data",
            "input = rand_samples()\n"
            "output = stream_sink((input,_samples))")

spk_extract = ("Extract spikes from raw neural recordings",
                 "input = arf_reader()\n"
                 "scaled = zscale(input)\n")
                 # "spikes = spike_detect(hpass)\n"
                 # "output = file_writer(spikes)")


# Variables:
# End:
