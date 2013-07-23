# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Plotting modules

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul 23 15:06:17 2013
"""

import logging
from mspikes import util
from mspikes.types import Node, tag_set


class collect_stats(Node):
    """Collect statistics from upstream modules"""

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--plot",
                 help="if set, plot results",
                 action="store_true")

    def __init__(self, **options):
        util.set_option_attributes(self, options, plot=True)
        self._stats = []

    def send(self, chunk):
        if "scalar" in chunk.tags:
            for field, value in chunk.data._asdict().iteritems():
                self._stats.append((float(chunk.offset), chunk.id, field, value))

    def close(self):
        import numpy as nx
        names = ('time','chan','stat','value')
        data = nx.rec.fromrecords(self._stats, names=names)
        if self.plot:
            import matplotlib.pyplot as plt
            # remap strings to numbers
            channels = tuple(set(data['chan']))
            stats = tuple(set(data['stat']))
            fig = plt.figure()
            for i,stat in enumerate(stats):
                ax = fig.add_subplot(len(stats), 1, i + 1)
                ax.hold(1)
                for j,chan in enumerate(channels):
                    idx = (data['chan']==chan) & (data['stat']==stat)
                    ax.plot(data['time'][idx], data['value'][idx], label=chan)
                ax.set_ylabel(stat)
                ax.legend()
            fig.show()
            plt.show()
        else:
            print "\t".join(names)
            for rec in data:
                print "\t".join("%s" % x for x in rec)




# Variables:
# End:
