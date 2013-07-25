# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Plotting modules

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul 23 15:06:17 2013
"""

from mspikes import util
from mspikes.types import Node, tag_set


class print_stats(Node):
    """ Print statistics from upstream modules """

    def __init__(self, **options):
        names = ('time','chan','stat','value')
        print "\t".join(names)

    def send(self, chunk):
        if not "scalar" in chunk.tags: return
        for field, value in chunk.data._asdict().iteritems():
            print "%.3f\t%s\t%s\t%f" % (float(chunk.offset), chunk.id, field, value)

try:
    import matplotlib.pyplot as plt
except ImportError:
    class plot_stats(Node):
        """Plot statistics from upstream module (disabled; needs matplotlib)"""
else:
    class plot_stats(Node):
        """Plot statistics from upstream modules"""

        @classmethod
        def options(cls, addopt_f, **defaults):
            # TODO restrict to specific stats?
            pass

        def __init__(self, **options):
            plt.ion()
            self.fig = None
            self.colors = {}

        def send(self, chunk):
            if not "scalar" in chunk.tags: return
            if self.fig is None:
                self.fig, self.axes = plt.subplots(len(chunk.data),1, sharex=True, squeeze=True)
                self.axes[-1].set_xlabel("Time (s)")
                for name, ax in zip(chunk.data._fields, self.axes):
                    ax.set_ylabel(name)
                    ax.hold(1)

            for datum, ax in zip(chunk.data, self.axes):
                if chunk.id in self.colors:
                    ax.plot(chunk.offset, datum, '.', color=self.colors[chunk.id], label=chunk.id)
                else:
                    p = ax.plot(chunk.offset, datum, '.', label=chunk.id)
                    self.colors[chunk.id] = p[0].get_color()
                    ax.legend(fontsize='small')
            plt.draw()

        def close(self):
            if plt.isinteractive():
                plt.ioff()
                plt.show()


# Variables:
# End:
