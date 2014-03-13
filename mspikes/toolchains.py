# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Predefined toolchains.

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jun 19 09:55:10 2013
"""

view_stats = ("Inspect raw sampled data",
              "input = arf_reader()\n"
              "scaled = zscale(input)\n"
              "view = plot_stats(scaled)")

spk_extract = ("Extract spikes from raw neural recordings",
               "input = arf_reader()\n"
               "scaled = zscale(input)\n"
               "spikes = spike_extract(scaled)\n"
               "output = arf_writer(spikes)")

klust_export = ("Export spike features for klusters/KlustaKwik",
                "input = arf_reader()\n"
                "feats = spike_features((input, _events))\n"
                "output = klusters_writer(feats)")

klust_import = ("Import sorted spikes from klusters",
                "input = klusters_reader()\n"
                "output = arf_writer(input)")

json_export = ("Export event times to json files",
               "input = arf_reader()\n"
               "output = json_writer(input)")

exclude_entries = ("Mark entries as unusable in an arf file",
                   "input = arf_reader(writable=True)\n"
                   "excl = entry_excluder(input)\n"
                   "output = arf_writer(excl, append_entries=True)")

# Variables:
# End:
