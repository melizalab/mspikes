#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
# Free for use under Creative Commons Attribution-Noncommercial-Share
# Alike 3.0 United States License
# (http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
spike_extract - extracts spike times and features from extracellular data

Usage: spike_extract [OPTIONS] <sitefile.arf>

Options:

 --chan CHANNELS : specify which channels to analyze. If multiple
 -c CHANNELS       channels were recorded, these can be specified and
                   grouped using the --chan flag.  For example,
                   --chan='1,5,7' will extract spikes from channels
                   1,5, and 7.  Channel groups are currently not supported.

 -r/-a THRESHS:    specify dynamic/absolute thresholds for spike
                   extraction.  Either one value for all channels, or
                   a quoted, comma delimited list, like '6.5,6.5,5'

 -t/-T RMS:        limit analysis to episodes where the total rms is less
                   than <max_rms>.  Use -t to calculate total rms
                   across specified channels; use -T to calculate rms
                   across all valid channels.
                   
 -i [CHANS]:       invert data from specific channels (all if unspecified)

 -f NFEATS:        how many principal components and their
                   projections to calculate (default 3 per channel).
 -R:               include raw features

 -w WINDOW:        number of points on either side of the spike
                   to analyze (default 20)

 --kkwik:          run KlustaKwik on each group after it's extracted

 Outputs a number of files that can be used with Klusters or KlustaKwik.
   <sitefile>.spk.<g> - the spike file
   <sitefile>.fet.<g> - the feature file
   <sitefile>.clu.<g> - the cluster file (all spikes assigned to one cluster)
   <sitefile>.xml - the control file used by Klusters

 To do simple thresholding, use the following flag:
 --simple:         extract spike times directly to arf file. Ignores -f,-w,
                   and --kkwik flags

"""

# docstring for tetrode grouping
#If recording from tetrodes, grouping can be done with parentheses: e.g. --chan='(1,2,3,4),(5,6,7,8)'

import os, sys, getopt, pdb
from mspikes import __version__
import arf
import extractor, klusters

options = {
    'thresholds' : [4.5],
    'abs_thresh' : False,
    'rms_all_chans' : False,
    'nfeats' : 3,
    'measurements' : (),
    'window' : 20,
    'channels' : [0],
    'inverted' : (),
    'kkwik': False,
    'simple' : False,
    'resamp' : 3,
    'refrac' : 20,
    }

def simple_extraction(arffile, log=None, **options):
    """
    For each channel, run through all the entries in the arf file,
    extract the spike times based on simple thresholding, and create a
    new channel with the spike times.

    arffile: the file to analyze. opened in append mode, so be careful
             about accessing it before this function terminates
    log: if not None, output some status information here
    """
    channels = options.get('channels')
    threshs = options.get('thresholds')
    with arf.arf(arffile,'a') as arfp:
        for channel,thresh in zip(channels,threshs):
            if log: log.write("Extracting spikes from channel %d at thresh %3.2f (%s) " % \
                              (channel, thresh, "abs" if options['abs_thresh'] else "rms"))
            attributes = dict(units='s', datatype=arf.DataTypes.SPIKET,
                               method='threshold', threshold=thresh, window=options['window'],
                               inverted=channel in options['inverted'], resamp=options['resamp'],
                               refrac=options['refrac'], mspikes_version=__version__,)
            spikecount = 0
            for entry, times, spikes in extractor.extract_spikes(arfp, channel, thresh, **options):
                chan_name = entry.get_record(channel)['name'] + '_thresh'
                entry.add_data((times,), chan_name, replace=True, **attributes)
                spikecount += times.size
                if log:
                    log.write(".")
                    log.flush()
            if log: log.write(" %d events\n" % spikecount)
        

def klusters_extraction(arffile, log=None, **options):
    """
    For each channel, run through all the entries in the arf
    file. Extract the spike waveforms and compute principal components
    and any other measurements. Creates the files used by
    klusters/klustakwik for spike sorting.

    arffile: the file to analyze
    """
    from numpy import concatenate, column_stack, sum, diff
    channels = options.get('channels')
    threshs = options.get('thresholds')
    basename = os.path.splitext(arffile)[0]
    with klusters.klustersite(basename, **options) as ks:
        with arf.arf(arffile,'r') as arfp:
            tstamp_offset = min(long(x[1:]) for x in arfp._get_catalog().cols.name[:])
            for channel,thresh in zip(channels,threshs):
                if log: log.write("Extracting spikes from channel %d at thresh %3.2f (%s) " % \
                                  (channel, thresh, "abs" if options['abs_thresh'] else "rms"))
                alltimes = []
                allspikes = []
                spikecount = 0
                for entry, times, spikes in extractor.extract_spikes(arfp, channel, thresh, **options):
                    times *= 20000
                    times += float(long(entry.record['name'][1:]) - tstamp_offset)
                    alltimes.append(times)
                    allspikes.append(spikes)
                    lastt = times[-1]
                    spikecount += times.size
                    if log:
                        log.write(".")
                        log.flush()
                if log: log.write(" %d events\n" % spikecount)
                if log: log.write("Aligning spikes\n")
                spikes_aligned = extractor.align_spikes(concatenate(allspikes,axis=0), **options)
                if log: log.write("Calculating features\n")
                spike_projections = extractor.projections(spikes_aligned, **options)[0]
                spike_measurements = extractor.measurements(spikes_aligned, **options)
                if spike_measurements:
                    spike_features = column_stack((spike_projections, spike_measurements, concatenate(alltimes)))
                else:
                    spike_features = column_stack((spike_projections, concatenate(alltimes)))

                if log: log.write("Writing data to klusters group %s.%d\n" % (basename, ks.group))
                ks.addevents(spikes_aligned, spike_features)
                ks.group += 1

def channel_options(options):
    """
    Validate channel and threshold options.  Modifies options in
    place.
    """
    channels = options.get('channels')
    thresh = options.get('thresholds')
    if not all(isinstance(x,int) for x in channels):
        raise ValueError, "Channels must be integers"  # fix this when we support groups
    if len(thresh)==1:
        thresh *= len(channels)
    if len(thresh) != len(channels):
        raise ValueError, "Channels and thresholds not the same length"
    options['thresholds'] = thresh
        

if __name__=="__main__":

    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:r:a:t:T:i:f:Rw:",
                                   ["chan=","simple","help","kkwik","version"])
    except getopt.GetoptError, e:
        print "Error: %s" % e
        sys.exit(-1)

    for o,a in opts:
        if o in ('-h','--help'):
            print __doc__
            sys.exit(0)
        elif o == '--version':
            print "%s version: %s" % (os.path.basename(sys.argv[0]), __version__)
            sys.exit(0)
        elif o in ('-c','--chan'):
            #exec "chans = [%s]" % a
            options['channels'] = tuple(int(x) for x in a.split(','))
        elif o in ('-r','-a'):
            options['thresholds'] = tuple(float(x) for x in a.split(','))
            if o == '-a': options['abs_thresh'] = True
        elif o in ('-t','-T'):
            options['max_rms'] = float(a)
            if o == '-T': options['rms_all_chans'] = True
        elif o == '-i':
            options['inverted'] = tuple(int(x) for x in a.split(','))
        elif o == '-f':
            options['nfeats'] = int(a)
        elif o == '-R':
            options['measurements'] = extractor._default_measurements
        elif o == '-w':
            options['window'] = int(a)
        elif o == '--kkwik':
            options['kkwik'] = True
        elif o == '--simple':
            options['simple'] = True

    if len(args) != 1:
        print "Error: no input file specified"
        sys.exit(-1)

    channel_options(options)
    print options
    if options['simple']:
        simple_extraction(args[0], log=sys.stdout, **options)
    else:
        klusters_extraction(args[0], log=sys.stdout, **options)
