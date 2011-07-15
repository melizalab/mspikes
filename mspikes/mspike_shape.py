#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
mspike_spikeshapes: get mean spike shapes for all units at a site.

Usage: mspike_spikeshapes [OPTIONS] <sitefile.arf>

Options:

-w:       window size (in samples; default 30)
-r:       resample spikes after extraction (default 3x)
-u UNITS: restrict to specific units (by name, comma delimited)

Uses spike time data stored in the ARF file (i.e. generated by
mspike_extract --simple or mspike_group -a).  Iterates through the
entries in <sitefile.arf> and extracts the spike waveforms associated
with the units in each entry.  Specific units can be extracted using
the -u flag.  The waveforms are extracted from the first channel
associated with a spike.

Output:

<sitename>.spikes: An ASCII-encoded file with the mean spikes in
tabular format.  The first column is the time, and each additional
column is the amplitude of one of the units.
"""
import os, sys, arf
from arf.constants import DataTypes
from extractor import __version__, _dummy_writer, _default_samplerate

options = {
    'window' : 30,
    'units' : None,
    'resamp' : 3
    }

def extract_spikes(arffile, log=_dummy_writer, **options):
    """
    For each unit defined in a site, extract the spike waveforms from
    the first channel associated with that unit.

    window:   size of the window to extract
    units:    restrict to specific units (by name)

    Returns dict of numpy arrays (nevents x nsamples), indexed by unit name
    """
    from collections import defaultdict
    from spikes import extract_spikes
    from numpy import round, row_stack
    units = options.get('units',None)
    window = options.get('window',30)

    out = defaultdict(list)
    log.write('* Extracting spike waveforms ')
    with arf.arf(arffile,'r') as arfp:
        sampling_rate = arfp.get_attributes(key='sampling_rate') or _default_samplerate
        for entry in arfp:
            channels = entry.catalog.read()
            for chan in channels:
                if chan['datatype'] != DataTypes.SPIKET: continue
                name,col,node = (chan[x] for x in ('name','column','node'))
                if units is not None and name not in units: continue
                src_chans = arfp.get_attributes(getattr(entry,node),'source_channels')
                src_chan = channels[src_chans[col][0]]['name']
                data,Fs = entry.get_data(src_chan)
                spiket = round(entry.get_data(name) * Fs / 1000).astype('i')
                if spiket.size > 0:
                    spikes = extract_spikes(data, spiket, window)
                    out[name].append(spikes)
            log.write('.')
            log.flush()
    log.write(' done\n')
    for k,v in out.items():
        out[k] = row_stack(v)
    return out, sampling_rate

def average_spikes(spikes, **options):
    from extractor import fftresample, align_spikes
    spikes = fftresample(spikes, spikes.shape[1] * options['resamp'])
    return align_spikes(spikes, **options).mean(0)

def write_spikes(sitename, spikes, **options):
    from numpy import savetxt, rec, arange
    fname = os.path.splitext(sitename)[0] + '.spikes'

    win_size = (options['window']-1) * 1000. / options['sampling_rate']
    time = arange(-win_size, win_size, 1000. / options['sampling_rate'] / options['resamp'])
    D = rec.fromarrays([time] + spikes.values(), names=['time']+spikes.keys())
    with open(fname,'wt') as fp:
        fp.write("# program: mspikes_shape\n")
        fp.write("# version: %s\n" % __version__)
        fp.write("# site file: %s\n" % sitename)
        fp.write("# window size: %d\n" % options['window'])
        fp.write("# resampling: %d\n" % options['resamp'])
        fp.write("# number of units: %d\n" % len(spikes))
        fp.write("time\t")
        units = spikes.keys()
        fp.write("\t".join(units))
        fp.write("\n")
        savetxt(fp, D)


def main(argv=None):
    import getopt
    if argv==None: argv = sys.argv
    print "* Program: %s" % os.path.split(argv[0])[-1]
    print "* Version: %s" % __version__

    opts, args = getopt.getopt(argv[1:], "w:r:u:h",
                               ["help","version"])
    try:
        for o,a in opts:
            if o in ('-h','--help'):
                print __doc__
                return 0
            elif o == '--version':
                print "%s version: %s" % (os.path.basename(argv[0]), __version__)
                return 0
            elif o == '-w':
                options['window'] = int(a)
            elif o == '-r':
                options['resamp'] = int(a)
            elif o == '-u':
                options['units'] = a.split(',')
    except ValueError, e:
        print "* Error: can't parse %s option (%s): %s" % (o,a,e)
        return -1

    if len(args) < 1:
        print "* Error: no input file specified"
        return -1
    print "* Input file: %s" % args[0]

    spikes,Fs = extract_spikes(args[0], log=sys.stdout, **options)
    sys.stdout.write("* Aligning waveforms\n")
    mean_spikes = dict((k,average_spikes(s, **options)) for k,s in spikes.items())
    options['sampling_rate'] = Fs
    write_spikes(args[0], mean_spikes, **options)


if __name__=="__main__":
    sys.exit(main())

# Variables:
# End:

