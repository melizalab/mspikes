# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Modules to collect statistics from data streams

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Tue Jul 23 15:06:17 2013
"""
import logging
from mspikes.types import Node


class arf_jitter(Node):
    """ Calculate jitter of source file in offset vs timestamp """

    def __init__(self):
        self._log = logging.getLogger("%s.%s" % (__name__, type(self).__name__))
        self.diffs = []
        self.prev = None

    def send(self, chunk):
        from numpy import dot, array
        if "structure" not in chunk.tags:
            return

        usec = dot(chunk.data['timestamp'], (1000000, 1))
        t = array((chunk.offset * 1000000, usec), dtype='int64')
        if self.prev is None:
            self.prev = t
        else:
            self.diffs.append(t - self.prev)
            self.prev = t

    def close(self):
        from numpy import asarray
        x = asarray(self.diffs)
        diffs = x[:,1] - x[:,0]
        self._log.info("sample clock vs system clock: drift=%.3f us, jitter=%.3f us",
                       diffs.mean(), diffs.std())


class print_stats(Node):
    """ Print scalar statistics from upstream modules """

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
        """Plot scalar statistics from upstream module (disabled; needs matplotlib)"""
        pass
else:
    class plot_stats(Node):
        """Plot scalar statistics from upstream modules"""

        @classmethod
        def options(cls, addopt_f, **defaults):
            # TODO restrict to specific stats?
            pass

        def __init__(self, **options):
            plt.ion()
            self.fig = None
            self.plots = {}

        def send(self, chunk):
            from numpy import append
            if not "scalar" in chunk.tags: return
            if self.fig is None:
                self.fig, self.axes = plt.subplots(len(chunk.data),1, sharex=True, squeeze=True)
                self.axes[-1].set_xlabel("Time (s)")
                for name, ax in zip(chunk.data._fields, self.axes):
                    ax.set_ylabel(name)
                    ax.hold(1)
                self.last_time = chunk.offset

            for datum, ax in zip(chunk.data, self.axes):
                try:
                    p = self.plots[chunk.id]
                except KeyError:
                    p = ax.plot(chunk.offset, datum, '.', label=chunk.id)
                    self.plots[chunk.id] = p[0]
                    # ax.legend(fontsize='small')
                else:
                    p.set_xdata(append(p.get_xdata(), chunk.offset))
                    p.set_ydata(append(p.get_ydata(), datum))

            if chunk.offset - self.last_time > 20:
                plt.draw()
                # FIXME
                self.last_time = chunk.offset

        def close(self):
            if plt.isinteractive():
                plt.ioff()
                plt.show()


# Variables:
# End:
