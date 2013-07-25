# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Predefined toolchains.

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:55:10 2013
"""

view_stats = ("Inspect raw sampled data",
              "input = arf_reader()\n"
              "scaled = zscale(input, exclude=True)\n"
              "view = collect_stats(scaled, plot=True)")

spk_extract = ("Extract spikes from raw neural recordings",
               "input = arf_reader()\n"
               "scaled = zscale(input)\n"
               "spikes = spike_extract(scaled)\n"
               "output = arf_writer(spikes)")

klust_export = ("Export spike features for klusters/KlustaKwik",
                "input = arf_reader()\n"
                "feats = spike_features((input, _events))\n"
                "output = klusters_writer(feats)")


# Variables:
# End:
