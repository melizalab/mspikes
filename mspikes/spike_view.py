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

import os
import arf
from extractor import __version__, _default_samplerate
import itertools

options = {
    'channels' : None,
    'units' : None,
    'plot_stats': False,
    }

def entry_stats(arffile, **options):
    """ Calculate RMS of each entry for each channel """
    from collections import defaultdict
    from spikes import signal_stats
    from numpy import ones, nan
    channels = options.get('channels',None)

    with arf.arf(arffile,'r') as arfp:
        sr = arfp.get_attributes(key='sampling_rate') or _default_samplerate
        etime = arfp._get_catalog().cols.timestamp[:]
        etime -= etime.min()
        stats = defaultdict(lambda : ones(etime.size) * nan)
        for i,entry in enumerate(arfp):
            for channel in entry._get_catalog():
                cname = channel['name']
                if channels is not None and cname not in channels: continue
                if channel['datatype'] == arf.DataTypes.EXTRAC_HP:
                    data,Fs = entry.get_data(cname)
                    mean,rms = signal_stats(data)
                    stats[cname][i] = rms
    return etime, dict(stats)

def plot_stats(arffile, **options):
    import matplotlib.pyplot as plt
    time,stats = entry_stats(arffile, **options)
    nchan = len(stats)

    fig = plt.figure()
    grid = [fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
    fig.subplots_adjust(hspace=0.)
    for i,k in enumerate(sorted(stats.keys())):
        grid[i].plot(time,stats[k],'o')
    plt.setp(grid[:-1],'xticks',[])

    return fig

class dataiter(object):
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
        if self.position == self.arfp.nentries - 1 : raise StopIteration, "Reached end of ARF file"
        self.position += 1
        entry = self.arfp[self.position]
        if self.position not in self.cache:
            self._load_data(entry)
        return entry, self.cache[self.position]

    def prev(self):
        if self.position <= 0: raise StopIteration, "Reached beginning of ARF file"
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

    
def plot_waveforms(arffile, **options):
    import matplotlib.pyplot as plt

    datag = iter_data(arffile, **options)

    #def next_
    entry,data = datag.next()
    nchan = len(data)

    fig = plt.figure()
    grid = [fig.add_subplot(nchan,1,i+1) for i in xrange(nchan)]
    fig.subplots_adjust(hspace=0.)
    for i,k in enumerate(sorted(data.keys())):
        grid[i].plot(data[k]['pcm'])

    return fig
                    
    

## from pylab import figure, setp, connect, show, ioff, draw

# colors used in labelling spikes
_manycolors = ['b','g','r','#00eeee','m','y',
               'teal',  'maroon', 'olive', 'orange', 'steelblue', 'darkviolet',
               'burlywood','darkgreen','sienna','crimson',
               ]

colorcycle = itertools.cycle(_manycolors)

def plotentry(k, entry, channels=None, eventlist=None, fig=None):
    atime = k.getentrytimes(entry)
    stim = k.getstimulus(atime)['name']
    files = k.getfiles(atime)
    files.sort(order='channel')
    pfp = []
    for f in files:
        fp = _fcache[f['filebase'].tostring()]
        fp.entry = f['entry']
        pfp.append(fp)
    if channels==None:
        channels = files['channel'].tolist()

    nplots = len(channels)
    # clear the figure and create subplots if needed
    if fig==None:
        fig = figure()

    ax = fig.get_axes()

    if len(ax) != nplots:
        fig.clf()
        ax = []
        for i in range(nplots):
            ax.append(fig.add_subplot(nplots,1,i+1))
        fig.subplots_adjust(hspace=0.)

    for i in range(nplots):
        s = pfp[channels[i]].read()
        t = nx.linspace(0,s.shape[0]/k.samplerate,s.shape[0])
        mu,rms = signalstats(s)
        y = (s - mu)/rms

        ax[i].cla()
        ax[i].hold(True)
        ax[i].plot(t,y,'k')
        ax[i].set_ylabel("%d" % channels[i])
        if eventlist!=None:
            plotevents(ax[i], t, y, entry, eventlist)

    # fiddle with the plots a little to make them pretty
    for i in range(len(ax)-1):
        setp(ax[i].get_xticklabels(),visible=False)

    ax[0].set_title('site_%d_%d (%d) %s' % (k.site + (entry,stim)))
    ax[-1].set_xlabel('Time (ms)')
    draw()
    return fig


def plotevents(ax, t, y, entry, eventlist):
    for j in range(len(eventlist)):
        idx = nx.asarray(eventlist[j][entry],dtype='i')
        times = t[idx]
        values = y[idx]
        p = ax.plot(times, values,'o')
        p[0].set_markerfacecolor(colorcycle(j))

def main():
    import sys, getopt
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:u:h",
                                   ["chan=","unit=","stats","help","version"])
    except getopt.GetoptError, e:
        print "Error: %s" % e
        sys.exit(-1)

    for o,a in opts:
        if o in ('-h','--help'):
            print __doc__
            sys.exit(0)
        elif o == '--version':
            print "%s version: %s" % (os.path.basename(sys.argv[0]), extractor.__version__)
            sys.exit(0)
        elif o in ('-c','--chan'):
            options['channels'] = tuple(int(x) for x in a.split(','))
        elif o in ('-u','--unit'):
            if len(a) > 0:
                options['units'] = tuple(int(x) for x in a.split(','))
            else:
                options['units'] = ''  # try to figure out unit-channel match
        elif o == '--stats':
            options['plot_stats'] = True
    
    if len(args) != 1:
        print "Error: no input file specified"
        sys.exit(-1)

    if options['plot_stats']:
        plot_stats(args, **options)
    else:
        plot_waveforms(args, **options)

####  SCRIPT
if __name__=="__main__":

    ### STATS:
    if opts.has_key('--stats'):
        # stats mode computes statistics for the site
        m,rms,t = klusters.sitestats(k, channels=chans)
        if rms.ndim > 1:
            rms = rms.mean(1)
        # plot them
        fig = figure()
        ax = fig.add_subplot(111)
        ax.plot(rms,'o')
        ax.set_xlabel('Entry')
        ax.set_ylabel('RMS')
        show()

    ### INSPECT:
    else:

        if opts.has_key('--units') and (k.nchannels==1 or (chans != None and len(chans)==1)):
            events = extractevents(opts['--units'], k)
        else:
            events = None

        def keypress(event):
            if event.key in ('+', '='):
                keypress.currententry += 1
                plotentry(k, keypress.currententry, channels=chans, eventlist=events, fig=fig)
            elif event.key in ('-', '_'):
                keypress.currententry -= 1
                plotentry(k, keypress.currententry, channels=chans, eventlist=events, fig=fig)

        keypress.currententry = int(opts.get('-e','0'))
        fig = plotentry(k, keypress.currententry, channels=chans, eventlist=events)
        connect('key_press_event',keypress)
        show()


    del(k)
