#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
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

C. Daniel Meliza, 2011
"""

import os, sys, posixpath
import arf
from .extractor import _default_samplerate, _dummy_writer
from .version import version
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid.parasite_axes import SubplotHost

options = {
    'channels' : None,
    'units' : None,
    'plot_stats': False,
    'entry' : 0,
    }

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
    import matplotlib.pyplot as plt
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

    return fig

class arfcache(object):
    """
    Provides backwards/forwards iteration through arf file, returning
    data in the EXTRAC_HP channels and attempting to annotate them
    with the appropriate spike data.

    Yields: {c1name:{'pcm':c1,u1name:u1a,u1bname:u1b,...},...}
    """

    def __init__(self, arfp, **options):
        self.channels = options.get('channels',None)
        self.units = options.get('units',None)
        self.arfp = arfp
        # need to sort entries by abstime
        self.entries = [k for k,e in arfp.items('sample_count')]
        self.position = options.get('entry',0) - 1

    def next(self):
        if self.position + 1 >= self.arfp.nentries:
            self.position = -1
        self.position += 1
        entry = self.entries[self.position]
        return (entry, self.position,) + self._load_data(entry)

    def prev(self):
        if self.position <= 0:
            self.position = len(self.entries)
        self.position -= 1
        entry = self.entries[self.position]
        return (entry, self.position,) + self._load_data(entry)

    def _load_data(self, entry_name):
        from collections import defaultdict
        out = defaultdict(dict)
        entry = self.arfp[entry_name]
        for cname,channel in entry.iteritems():
            if channel.attrs['datatype'] == arf.DataTypes.EXTRAC_HP:
                if self.channels is not None and cname not in self.channels: continue
                data = entry.get_data(cname)
                out[cname]['pcm'] = data
                out[cname]['sampling_rate'] = channel.attrs['sampling_rate']
            elif channel.attrs['datatype'] == arf.DataTypes.SPIKET:
                if self.units is not None and cname not in self.units: continue
                if 'source_channels' in channel.attrs:
                    for sc in channel.attrs['source_channels']:
                        out[sc][cname] = entry.get_data(cname)[0]
        return entry.attrs.get('protocol',''), dict(out)

class plotter(object):

    def __init__(self, arfp, **options):
        self.cache = arfcache(arfp, **options)
        self.create_figure()
        self.entry_data = self.cache.next()

    def create_figure(self):
        plt.rcParams['path.simplify'] = False
        plt.rcParams['axes.hold'] = False
        self.fig = plt.figure()
        self.fig.canvas.mpl_connect('key_press_event',self.keypress)

    def keypress(self, event):
        if event.key in ('+', '='):
            self.entry_data = self.cache.next()
            self.update()
        elif event.key in ('-', '_'):
            self.entry_data = self.cache.prev()
            self.update()
        elif event.key in ('q','Q','c'):
            plt.close(self.fig)

    def update(self):
        from numpy import linspace
        if self.entry_data is None: return
        entry_name,entry_num,protocol,data = self.entry_data
        nchan = len(data)
        grid = self.fig.axes
        if len(grid) != nchan:
            self.fig.clf()
            grid = [self.fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
            self.fig.subplots_adjust(hspace=0.)
        if len(data) < 1:
            if options.get('channels',None) is not None:
                raise RuntimeError, "No valid channels specified"
            else:
                raise RuntimeError, "Data does not have any extracellular highpass type channels -- try specifying manually"
        for i,k in enumerate(sorted(data.keys())):
            d = data[k]['pcm']
            Fs = data[k]['sampling_rate'] / 1000.
            t = linspace(0, d.size/Fs, d.size)
            stuff = [t,d,'k']
            for q,times in data[k].items():
                if q not in ('pcm','sampling_rate'):
                    ind = t.searchsorted(times)
                    stuff.extend((times,d[ind],'o'))
            grid[i].plot(*stuff)
            grid[i].set_xlim((0,d.size/Fs))
            grid[i].set_ylabel(k)
            # to do: add RMS scale

        plt.setp(grid[:-1], 'xticklabels', '')
        grid[0].set_title('entry %d: %s (%s)' % (entry_num, entry_name, protocol))
        grid[-1].set_xlabel('Time (ms)')
        self.fig.canvas.draw()


def main(argv=None):
    import getopt
    if argv==None: argv = sys.argv
    opts, args = getopt.getopt(argv[1:], "c:u:e:hv",
                               ["chan=","unit=","stats","help","version"])

    print "* Program: %s" % os.path.split(argv[0])[-1]
    print "* Version: %s" % version

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
    print "* Input file: %s" % args[0]


    try:
        with arf.file(args[0],'r') as arfp:
            if options['plot_stats']:
                plot_stats(arfp, log=sys.stdout, **options)
            else:
                pltter = plotter(arfp, **options)
                pltter.update()
            plt.show()
            print "* Exiting"
        return 0
    except RuntimeError, e:
        print e
        return -1

if __name__=="__main__":
    sys.exit(main())

# Variables:
# End:
