#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) Dan Meliza, 2006-2012 (dmeliza@uchicago.edu)
# Free for use under Creative Commons Attribution-Noncommercial-Share
# Alike 3.0 United States License
# (http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
mspike_view - inspect waveforms and statistics of pcm spike data

Usage: spike_view [OPTIONS] <sitefile.arf>

 --stats:     Plot total RMS for each channel. Otherwise plot raw waveforms.
              This is a computationally intensive operation for multichannel data.

 --chan CHANNELS : specify which channels to analyze, multiple channels
 -c CHANNELS       as a list, using channel names. For example, --chan='ch11,ch15'
                   will plot data from channels 'ch11' and 'ch15'. By default all channels
                   with data type EXTRAC_HP will be used.

 --unit UNITS :    specify channels with event time data to overlay on the raw
 -u UNITS          data (in waveform view only)

 -e ENTRY :        specify which entry [index] to start at (waveform view only)
"""

import os, sys
import arf
from .extractor import _dummy_writer
from .version import version
import matplotlib.pyplot as plt

options = {
    'channels' : None,
    'units' : None,
    'plot_stats': False,
    'entry' : 0,
    }

plot_options = {
    'path.simplify' : False,
    'axes.hold' : False,
    'ytick.direction' : 'in',
    'xtick.direction' : 'in',
}

spike_colors = ('b','r','g','m','c','y',
                'orchid','orange','salmon','tomato','seagreen','violet')


def natsorted(key):
    """ key function for natural sorting of channel names """
    import re
    return map(lambda t: int(t) if t.isdigit() else t, re.split(r"([0-9]+)",key))


def entry_stats(arfp, log=_dummy_writer, **options):
    """ Calculate RMS of each entry for each channel """
    from collections import defaultdict
    from spikes import signal_stats
    from numpy import ones, zeros, nan
    channels = options.get('channels',None)

    etime = zeros(arfp.nentries, dtype='i8')
    # we don't know at the start what the channel names are
    stats = defaultdict(lambda : ones(arfp.nentries) * nan)
    log.write("* Calculating statistics ")
    for i,(ename,entry) in enumerate(arfp.items()):
        etime[i] = entry.timestamp
        for cname,dset in entry.iteritems():
            if channels is None and dset.attrs['datatype'] != arf.DataTypes.EXTRAC_HP: continue
            if channels is None or cname in channels:
                data = entry.get_data(cname)
                mean,rms = signal_stats(data)
                stats[cname][i] = rms
        log.write(".")
        log.flush()
    log.write(" done\n")
    etime -= etime.min()
    return etime, dict(stats)

def plot_stats(arfp, **options):
    time,stats = entry_stats(arfp, **options)
    nchan = len(stats)
    if nchan < 1:
        if options.get('channels',None) is not None:
            raise RuntimeError, "No valid channels specified"
        else:
            raise RuntimeError, "Data does not have any extracellular highpass type channels -- try specifying manually"

    fig = plt.figure()
    grid = [fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
    fig.subplots_adjust(hspace=0.)
    for i,k in enumerate(sorted(stats.keys())):
        grid[i].plot(time,stats[k],'o')
        grid[i].set_ylabel(k)
    plt.setp(grid[:-1],'xticks',[])
    grid[0].set_title("RMS")
    grid[-1].set_xlabel("Time (s)")

    def kp(event):
        if event.key in ('m','M'):
            mgr = fig.get_current_fig_manager()
            if hasattr(mgr,'frame') and hasattr(mgr.frame,'Maximixe'):
                mgr.frame.Maximize(not mgr.frame.IsMaximized())
        elif event.key in ('q','Q','c'):
            plt.close(fig)

    fig.canvas.mpl_connect('key_press_event',kp)

    return fig

class arfcache(object):
    """ Provides backwards/forwards iteration through arf file, with wraparound """

    # TODO? provide cache ahead
    def __init__(self, arfp, **options):
        self.entries = [(k,e) for k,e in arfp.items('sample_count')]
        self.arfp = arfp
        self.position = options.get('entry',0)

    def next(self, step=1):
        self.position = (self.position + step) % self.arfp.nentries
        return self

    def prev(self, step=1):
        return self.next(-step)

    @property
    def value(self):
        return self.entries[self.position]


class plotter(object):

    def __init__(self, arfp, **options):
        self.cache = arfcache(arfp, **options)
        self.channels = options.get('channels',None)
        self.units = options.get('units',None)
        self.create_figure()

    def create_figure(self):
        self.fig = plt.figure()
        self.fig.canvas.mpl_connect('key_press_event',self.keypress)
        self.plot()

    def keypress(self, event):
        if event.key in ('+', '='):
            self.cache.next()
            self.plot()
        elif event.key in ('-', '_'):
            self.cache.prev()
            self.plot()
        elif event.key in ('m','M'):
            mgr = self.fig.get_current_fig_manager()
            # wx
            if hasattr(mgr,'frame') and hasattr(mgr.frame,'Maximixe'):
                mgr.frame.Maximize(not mgr.frame.IsMaximized())
            # macosx no equivalent?

        elif event.key in ('q','Q','c'):
            plt.close(self.fig)

    def plot(self):
        from numpy import arange
        from matplotlib.lines import Line2D
        ename,entry = self.cache.value
        osc_chans = [name for name,dset in entry.iteritems() if \
                         (self.channels is None or name in self.channels) and \
                         arf.arf.dataset_properties(dset)[0] == 'sampled']
        osc_chans.sort(key=natsorted)
        nchan = len(osc_chans)
        grid = self.fig.axes
        # TODO handle axes creation/destruction better
        if len(grid) != nchan:
            self.fig.clf()
            grid = [self.fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
            self.fig.subplots_adjust(hspace=0.02)

        for i,chan in enumerate(osc_chans):
            dset = entry[chan]
            t = arange(0.0, dset.shape[0]) * 1000. / dset.attrs['sampling_rate']
            grid[i].plot(t, dset, 'k', label="_nolegend_")
            grid[i].set_ylabel(chan)

        spk_chans = [name for name,dset in entry.iteritems() if \
                         (self.units is None or name in self.units) and \
                         dset.attrs.get('datatype',None) == arf.DataTypes.SPIKET]
        for j,chan in enumerate(spk_chans):
            dset = entry[chan]
            spiket = dset.value if dset.shape[0] > 0 else []
            for src_chan in dset.attrs.get('source_channels',[]):
                chan_ind = osc_chans.index(src_chan)
                if chan_ind < 0: continue
                # get osc data from plot
                ax = grid[chan_ind]
                t,d = ax.lines[0].get_xdata(), ax.lines[0].get_ydata()
                ind = t.searchsorted(spiket)
                p = Line2D(spiket, d[ind], ls='None', marker='o', c=spike_colors[j], label=chan)
                ax.add_line(p)

        for i,ax in enumerate(grid):
            ax.locator_params(tight=True,nbins=6)
            if len(ax.lines) > 1: ax.legend(numpoints=1, prop={'size':6})
            if i + 1 < nchan: ax.set_xticklabels('')
        grid[0].set_title('entry %d: %s (%s)' % (self.cache.position, ename, entry.attrs.get('protocol','')))
        grid[-1].set_xlabel('Time (ms)')
        self.fig.canvas.draw()


def main(argv=None):
    import getopt
    if argv==None: argv = sys.argv
    opts, args = getopt.getopt(argv[1:], "c:u:e:hv",
                               ["chan=","unit=","stats","help","version"])

    print "* Program:", os.path.split(argv[0])[-1]
    print "* Version:", version
    print "* Plotting backend:", plt.get_backend()

    try:
        for o,a in opts:
            if o in ('-h','--help'):
                print __doc__
                return 0
            elif o in ('-v','--version'):
                return 0
            elif o in ('-c','--chan'):
                options['channels'] = a.split(',')
            elif o in ('-u','--unit'):
                if len(a) > 0:
                    options['units'] = a.split(',')
                else:
                    options['units'] = ''  # try to figure out unit-channel match
            elif o == '-e':
                options['entry'] = int(a)
            elif o == '--stats':
                options['plot_stats'] = True
    except ValueError, e:
        print "* Error: can't parse %s option (%s): %s" % (o,a,e)
        return -1

    if len(args) < 1:
        print "* Error: no input file specified"
        return -1
    fname = args[0]
    if not os.path.exists(fname):
        print "* Error: %s does not exist" % fname
        return -1
    print "* Input file:", fname

    plt.rcParams.update(plot_options)
    try:
        with arf.file(fname,'r') as arfp:
            if options['plot_stats']:
                plot_stats(arfp, log=sys.stdout, **options)
            else:
                # retain instance or event bindings are lost
                x = plotter(arfp, **options)
            plt.show()
            print "* Exiting"
        return 0
    except IOError:
        print "* Error: unable to open", fname
    except RuntimeError, e:
        print "* Error:", e
        return -1

if __name__=="__main__":
    sys.exit(main())

# Variables:
# End:
