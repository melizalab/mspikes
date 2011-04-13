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
 -c CHANNELS       as a list, i.e. --chan='1,5,7' will plot data from channels
                   1,5, and 7

 --unit UNITS :    specify channels with event time data to overlay on the raw
 -u UNITS          data

C. Daniel Meliza, 2008
"""

import os, sys, itertools
import arf
from extractor import __version__, _default_samplerate, _dummy_writer
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid.parasite_axes import SubplotHost

options = {
    'channels' : None,
    'units' : None,
    'plot_stats': False,
    }

def entry_stats(arfp, log=_dummy_writer, **options):
    """ Calculate RMS of each entry for each channel """
    from collections import defaultdict
    from spikes import signal_stats
    from numpy import ones, nan
    channels = options.get('channels',None)

    sr = arfp.get_attributes(key='sampling_rate') or _default_samplerate
    etime = arfp._get_catalog().cols.timestamp[:]
    etime -= etime.min()
    stats = defaultdict(lambda : ones(etime.size) * nan)
    log.write("Calculating statistics ")
    for i,entry in enumerate(arfp):
        for channel in entry._get_catalog():
            cname = channel['name']
            if channels is not None and cname not in channels: continue
            if channel['datatype'] == arf.DataTypes.EXTRAC_HP:
                data,Fs = entry.get_data(cname)
                mean,rms = signal_stats(data)
                stats[cname][i] = rms
        log.write(".")
        log.flush()
    log.write(" done\n")
    return etime, dict(stats)

def plot_stats(arfp, **options):
    import matplotlib.pyplot as plt
    time,stats = entry_stats(arfp, **options)
    nchan = len(stats)

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
        self.cache = {}
        self.position = -1

    def next(self):
        if self.position + 1 >= self.arfp.nentries: raise StopIteration
        self.position += 1
        entry = self.arfp[self.position]
        if self.position not in self.cache:
            self._load_data(entry)
        return entry, self.cache[self.position]

    def prev(self):
        if self.position <= 0: raise StopIteration
        self.position -= 1
        entry = self.arfp[self.position]
        if self.position not in self.cache:
            self._load_data(entry)
        return entry, self.cache[self.position]

    def _load_data(self, entry):
        from collections import defaultdict
        out = defaultdict(dict)
        catalog = entry._get_catalog().read()
        for channel in catalog:
            cname = channel['name']
            if channel['datatype'] == arf.DataTypes.EXTRAC_HP:
                if self.channels is not None and cname not in self.channels: continue
                data,Fs = entry.get_data(cname)
                out[cname]['pcm'] = data
                out[cname]['sampling_rate'] = Fs
            elif channel['datatype'] == arf.DataTypes.SPIKET:
                if self.units is not None and cname not in self.units: continue
                node = getattr(entry,channel['node'])
                try:
                    for sc in node.attrs.source_channels[channel['column']]:
                        src_cname = catalog[sc]['name']
                        if src_cname in out:
                            out[src_cname][cname] = entry.get_data(cname)
                except:
                    pass
        self.cache[entry.index] = dict(out)

class plotter(object):

    def __init__(self, arfp, **options):
        self.cache = arfcache(arfp, **options)
        self.create_figure()
        self.entry, self.data = self.cache.next()

    def create_figure(self):
        plt.rcParams['path.simplify'] = False
        self.fig = plt.figure()
        self.fig.canvas.mpl_connect('key_press_event',self.keypress)

    def keypress(self, event):
        if event.key in ('+', '='):
            try:
                self.entry, self.data = self.cache.next()
                self.update()
            except:
                pass
        elif event.key in ('-', '_'):
            try:
                self.entry,self.data = self.cache.prev()
                self.update()
            except:
                pass

    def update(self):
        from numpy import linspace
        if self.entry is None: return
        nchan = len(self.data)
        grid = self.fig.axes
        if len(grid) != nchan:
            self.fig.clf()
            grid = [self.fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
            self.fig.subplots_adjust(hspace=0.)
        for i,k in enumerate(sorted(self.data.keys())):
            d = self.data[k]['pcm']
            Fs = self.data[k]['sampling_rate'] / 1000.
            t = linspace(0, d.size/Fs, d.size)
            stuff = [t,d,'k']
            for q,times in self.data[k].items():
                if q not in ('pcm','sampling_rate'):
                    ind = t.searchsorted(times)
                    stuff.extend((times,d[ind],'o'))
            grid[i].plot(*stuff)
            grid[i].set_xlim((0,d.size/Fs))
            grid[i].set_ylabel(k)
            # to do: add RMS scale

        plt.setp(grid[:-1], 'xticklabels', '')
        grid[0].set_title('entry %d: %s (%s)' % (self.entry.index, self.entry._v_name, self.entry.record['protocol']))
        grid[-1].set_xlabel('Time (ms)')
        self.fig.canvas.draw()
    

def main(argv=None):
    import getopt
    if argv==None: argv = sys.argv
    opts, args = getopt.getopt(argv[1:], "c:u:h",
                               ["chan=","unit=","stats","help","version"])

    for o,a in opts:
        if o in ('-h','--help'):
            print __doc__
            return 0
        elif o == '--version':
            print "%s version: %s" % (os.path.basename(argv[0]), __version__)
            return 0
        elif o in ('-c','--chan'):
            options['channels'] = a.split(',')
        elif o in ('-u','--unit'):
            if len(a) > 0:
                options['units'] = a.split(',')
            else:
                options['units'] = ''  # try to figure out unit-channel match
        elif o == '--stats':
            options['plot_stats'] = True
    
    if len(args) < 1:
        print "Error: no input file specified"
        return -1

    with arf.arf(args[0],'r') as arfp:
        if options['plot_stats']:
            plot_stats(arfp, log=sys.stdout, **options)
        else:
            pltter = plotter(arfp, **options)
            pltter.update()
        plt.show()
    return 0

if __name__=="__main__":
    sys.exit(main())
