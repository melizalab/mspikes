#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
# Free for use under Creative Commons Attribution-Noncommercial-Share
# Alike 3.0 United States License
# (http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
spike_extract - extracts spike times and features from extracellular data

Usage: spike_extract --chan|-c CHANNELS [OPTIONS] <sitefile.arf>


 --chan CHANNELS : specify which channels to analyze, multiple channels
 -c CHANNELS       as a list, i.e. --chan='ch11,ch15' will extract spikes
                   from channels named ch11 and ch15.  Channel groups/tetrodes
                   are not currently supported.
Optional arguments:

 -r/-a THRESHS:    specify dynamic/absolute thresholds for spike
                   extraction.  Either one value for all channels, or
                   a quoted, comma delimited list, like '6.5,6.5,5'

 -t    RMS:        limit analysis to episodes where the total rms is less
                   than RMS.  Specify one value for all channels, or
                   comma-delimited list to specify per channel.

 --start TIME:     only process episodes occurring between specified times,
 --stop TIME:      in units of seconds

 -i CHANNELS:      invert data from specific channels
 -I:               invert data from all channels

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

import os, sys
import arf
import extractor, klusters


options = {
    'thresholds' : [4.5],  # must be a sequence of scalars
    'abs_thresh' : False,  # determines how thresholds is interpreted
    'max_rms' : [None],    # must be a sequence of scalars, or None to set no threshold
    'start' : None,
    'stop' : None,
    'nfeats' : 3,
    'measurements' : (),
    'window' : 20,
    'channels' : [],
    'inverted' : (),    # can be True for all channels, or a sequence
    'kkwik': False,
    'simple' : False,
    'resamp' : extractor._spike_resamp,
    }

def channel_options(**options):
    """
    Validate channel-related options.  Raises a RuntimeError if
    lengths do not match.

    Returns channels, thresholds, rmsthresholds, inversions
    """
    channels = options.get('channels')
    if len(channels) < 1:
        raise RuntimeError, "Specify at least one channel"

    thresh = options.get('thresholds')
    if len(thresh)==1:
        thresh *= len(channels)
    elif len(thresh) != len(channels):
        raise RuntimeError, "Specify one spike threshold for all channels, or one for each channel"

    maxrms = options.get('max_rms')
    if len(maxrms)==1:
        maxrms *= len(channels)
    elif len(maxrms) != len(channels):
        raise RuntimeError, "Specify one spike threshold for all channels, or one for each channel"

    inverted = options.get('inverted')  # may be True
    if inverted is True:
        inverted = channels
    elif any(g not in channels for g in inverted):
        raise RuntimeError, "No match in inverted channel list -- did you mean -I?"

    return channels, thresh, maxrms, inverted


def simple_extraction(arffile, log=extractor._dummy_writer, **options):
    """
    For each channel, run through all the entries in the arf file,
    extract the spike times based on simple thresholding, and create a
    new channel with the spike times.

    arffile: the file to analyze. opened in append mode, so be careful
             about accessing it before this function terminates
    """
    channels,threshs,rmsthreshs,inverted = channel_options(**options)
    with arf.arf(arffile,'a') as arfp:
        for channel,thresh,maxrms in zip(channels,threshs,rmsthreshs):
            do_invert = channel in inverted
            attributes = dict(units='ms', datatype=arf.DataTypes.SPIKET,
                              method='threshold', threshold=thresh, window=options['window'],
                              source_channels=((channel,),),
                              inverted=do_invert, resamp=options['resamp'],
                              mspikes_version=extractor.__version__,)
            gen = extractor.extract_spikes(arfp, channel, thresh, maxrms, log, invert=do_invert,**options)
            for entry, times, spikes, Fs in gen:
                if times is not None and times.size > 0:
                    chan_name = channel + '_thresh'
                    entry.add_data((times * 1000. / Fs,), chan_name, replace=True, **attributes)


def klusters_extraction(arffile, log=extractor._dummy_writer, **options):
    """
    For each channel, run through all the entries in the arf
    file. Extract the spike waveforms and compute principal components
    and any other measurements. Creates the files used by
    klusters/klustakwik for spike sorting.

    arffile: the file to analyze
    """
    # commented lines in this function downsample the spike times to
    # the original sampling rate. This fixes an issue with klusters
    # where certain sampling rates cause horrible crashes, but throws
    # away the sub-sampling-interval precision of spike times.
    from numpy import concatenate, column_stack
    channels,threshs,rmsthreshs,inverted = channel_options(**options)
    options['thresholds'] = threshs
    basename = os.path.splitext(arffile)[0]

    kkwik_pool = []
    with arf.arf(arffile,'r') as arfp:
        sr = arfp.get_attributes(key='sampling_rate')
        if sr is None:
            sr = extractor._default_samplerate
            log.write("warning: %s was not generated by arfxplog, assume samplerate %d\n" % \
                      (arffile,sr))
        options['sampling_rate'] = sr
        with klusters.klustersite(basename, **options) as ks:
            tstamp_offset = min(long(x[1:]) for x in arfp._get_catalog().cols.name[:]) * options['resamp']
            #tstamp_offset = min(long(x[1:]) for x in arfp._get_catalog().cols.name[:])
            for channel,thresh,maxrms in zip(channels,threshs,rmsthreshs):
                alltimes = []
                allspikes = []
                gen = extractor.extract_spikes(arfp, channel, thresh, maxrms, log,
                                               invert=(channel in inverted), **options)
                for entry, times, spikes, Fs in gen:
                    if times is None:
                        # mark unused epochs by their record ID, since this guaranteed to be unique
                        ks.skipepochs(entry.record["recid"])
                    else:
                        times += long(entry.record['name'][1:])*options['resamp'] - tstamp_offset
                        #times /= options['resamp']
                        #times += long(entry.record['name'][1:]) - tstamp_offset
                        alltimes.append(times)
                        allspikes.append(spikes)
                        lastt = times[-1]

                if sum(x.size for x in alltimes) == 0:
                    log.write("*** No spikes: skipping channel\n")
                else:
                    alltimes = concatenate(alltimes)
                    klusters.check_times(alltimes)
                    log.write("*** Aligning spikes\n")
                    spikes_aligned = extractor.align_spikes(concatenate(allspikes,axis=0), **options)
                    log.write("*** Calculating features\n")
                    spike_projections = extractor.projections(spikes_aligned, **options)[0]
                    spike_measurements = extractor.measurements(spikes_aligned, **options)
                    if spike_measurements is not None:
                        spike_features = column_stack((spike_projections, spike_measurements, alltimes))
                    else:
                        spike_features = column_stack((spike_projections, alltimes))
                    ks.addevents(spikes_aligned, spike_features)
                    log.write("*** Wrote data to klusters group %s.%d\n" % (basename, ks.current_channel+1))
                    if options.get('kkwik',False):
                        log.write("*** Starting KlustaKwik\n")
                        kkwik_pool.append(ks.run_klustakwik())

                ks.current_channel += 1
        for i,job in enumerate(kkwik_pool):
            log.write("*** Waiting for KlustaKwik job %d to finish..." % i)
            log.flush()
            job.wait()
            log.write("done\n")


def main(argv=None):
    import getopt
    if argv==None: argv = sys.argv
    opts, args = getopt.gnu_getopt(argv[1:], "c:r:a:t:i:If:Rw:h",
                               ["chan=","start=","stop=","simple","help","kkwik","version"])

    print "* Program: %s" % os.path.split(argv[0])[-1]
    print "* Version: %s" % extractor.__version__

    try:
        for o,a in opts:
            if o in ('-h','--help'):
                print __doc__
                return 0
            elif o == '--version':
                print "%s version: %s" % (os.path.basename(argv[0]), extractor.__version__)
                return 0
            elif o in ('-c','--chan'):
                options['channels'] = a.split(',')
            elif o in ('-r','-a'):
                options['thresholds'] = tuple(float(x) for x in a.split(','))
                if o == '-a': options['abs_thresh'] = True
            elif o == '-t':
                options['max_rms'] = tuple(float(x) for x in a.split(','))
            elif o == '--start':
                options['start'] = float(a)
            elif o == '--stop':
                options['stop'] = float(a)
            elif o == '-i':
                options['inverted'] = a.split(',')
            elif o == '-I':
                options['inverted'] = True
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
    except ValueError, e:
        print "* Error: can't parse %s option (%s): %s" % (o,a,e)
        return -1

    if len(args) < 1:
        print "* Error: no input file specified"
        return -1
    print "* Input file: %s" % args[0]

    try:
        if options['simple']:
            simple_extraction(args[0], log=sys.stdout, **options)
        else:
            klusters_extraction(args[0], log=sys.stdout, **options)
        return 0
    except RuntimeError, e:
        print "* Error: %s" % e
        return -1


if __name__=="__main__":
    sys.exit(main())


# Variables:
# End:
