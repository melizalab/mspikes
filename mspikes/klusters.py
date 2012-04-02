# -*- coding: iso-8859-1 -*-
# -*- mode: python -*-
"""
Klusters/Klustakwik data are spread across several files, with
metadata stored in an xml file.  This module contains a class for
managing a collection of klusters data for a single site, and some
utility functions.

Copyright (C) Dan Meliza, 2006-2012 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
from collections import defaultdict
from .version import version

class klustersite(object):
    """
    Klusters data are organized into the following files:

    <base>.xml - the parameters file, describes which channels
                 are in which groups
    For each group <g>:
    <base>.spk.<g> - the spike file: 16-bit samples
    <base>.fet.<g> - the feature file
    <base>.clu.<g> - the cluster file (all spikes assigned to one cluster)
    """
    _spktemplate = "%s.spk.%d"
    _clutemplate = "%s.clu.%d"
    _fettemplate = "%s.fet.%d"

    def __init__(self, sitename, **kwargs):
        """
        Initialize a klusters site.

        sitename:   the basename for the files
        channels:   sequence of channel names
        thresh:     the threshold used to extract spikes (same length as channels)
        nfeats:     the number of PCA features per channel
        measurements:  the raw feature measurements
        window:     the number of samples per spike (automatically adjusted for resampling)
        sampling_rate:  the base sampling rate of the data (default 20000)
        resamp:         resampling factor for the spikes
        """
        self.sitename = sitename
        self.channels = tuple(kwargs['channels'])
        self.nsamples = 2 * kwargs['window'] * kwargs['resamp'] - kwargs['resamp'] * 2
        self.nfeatures = kwargs['nfeats'] + len(kwargs['measurements']) + 1
        self.nkfeats = kwargs['nfeats']
        self.thresh = kwargs['thresholds']
        self.samplerate = kwargs['sampling_rate'] * kwargs['resamp']
        self.skipped = [[] for x in self.channels]

        self.spk = defaultdict(self._openspikefile)
        self.clu = defaultdict(self._openclufile)
        self.fet = defaultdict(self._openfetfile)

        self.current_channel = 0

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.writexml()
        for v in self.spk.values(): v.close()
        for v in self.clu.values(): v.close()
        for v in self.fet.values(): v.close()

    @property
    def spikefile(self):
        return self._spktemplate % (self.sitename, self.current_channel + 1)

    @property
    def clufile(self):
        return self._clutemplate  % (self.sitename, self.current_channel + 1)

    @property
    def fetfile(self):
        return self._fettemplate % (self.sitename, self.current_channel + 1)

    def _openspikefile(self):
        """ Open handle to spike file """
        return open(self.spikefile,'wb')

    def _openclufile(self):
        fp = open(self.clufile,'wt')
        fp.write("1\n")
        return fp

    def _openfetfile(self):
        fp = open(self.fetfile,'wt')
        fp.write("%d\n" % self.nfeatures)
        return fp

    def writexml(self):
        """  Generate the xml file for the site """
        total_channels = len(self.channels)
        with open(self.sitename + ".xml", 'wt') as fp:
            fp.writelines(('<parameters creator="mspikes" version="%s" >\n' % version,
                           " <acquisitionSystem>\n",
                           "  <nBits>16</nBits>\n",
                           "  <nChannels>%d</nChannels>\n" % total_channels,
                           "  <samplingRate>%d</samplingRate>\n" % self.samplerate,
                           "  <voltageRange>20</voltageRange>\n",
                           "  <amplification>100</amplification>\n",
                           "  <offset>0</offset>\n",
                           " </acquisitionSystem>\n",
                           " <fieldPotentials>\n",
                           "  <lfpSamplingRate>1250</lfpSamplingRate>\n",
                           " </fieldPotentials>\n",
                           " <spikeDetection>\n",
                           "  <channelGroups>\n",))

            for i,channel in enumerate(self.channels):
                fp.write("   <group>\n    <channels>\n")
                fp.write("     <channel>%d</channel>\n" % i)
                fp.write("     <name>%s</name>\n" % channel)
                fp.write("     <thresh>%3.2f</thresh>\n" % self.thresh[i])
                fp.write("    </channels>\n")
                fp.write("    <nSamples>%d</nSamples>\n" % self.nsamples)
                fp.write("    <peakSampleIndex>%d</peakSampleIndex>\n" % (self.nsamples/2))

                fp.write("    <nFeatures>%d</nFeatures>\n" % (self.nfeatures))
                fp.write("    <skipped>\n    ")
                for etime in self.skipped[i]:
                    fp.write("<time>%d</time>" % etime)
                fp.write("\n    </skipped>\n")
                fp.write("   </group>\n")
            fp.write("  </channelGroups>\n </spikeDetection>\n</parameters>\n")

    def addevents(self, spikes, features):
        """
        Write events to the spk/clu/fet files in the current channel.
        Can be called more than once, although typically this is not
        very useful because realignment and PCA require all the spikes
        to be in memory.

        spikes: ndarray, nevents by nchannels by nsamples
                (or nevents by nsamples for 1 chan)
        features: ndarray, nevents by nfeatures
        """
        from numpy import savetxt
        assert spikes.shape[0] == features.shape[0], "Number of events in arguments don't match"
        assert features.shape[1] == self.nfeatures, \
               "Should have %d features, got %d" % (self.nfeatures, features.shape[1])
        spikes.astype('int16').tofile(self.spk[self.current_channel])
        savetxt(self.fet[self.current_channel], features, "%i")
        fp = self.clu[self.current_channel]
        for j in xrange(features.shape[0]): fp.write("1\n")

    def skipepochs(self, *epochs):
        """
        Mark one or more recording epochs as skipped; this information
        can be used later to determine if the absence of any spike
        times for an epoch is due to the epoch being skipped or not.

        epochs: a list of IDs for the epochs that were skipped
        """
        self.skipped[self.current_channel].extend(epochs)

    def run_klustakwik(self):
        """ Runs KlustaKwik on the current group """
        from subprocess import Popen
        nfeats = self.nkfeats
        totfeats = self.nfeatures
        self.fet[self.current_channel].close()
        self.clu[self.current_channel].close()
        cmd = ["KlustaKwik",self.sitename,str(self.current_channel+1),
               "-Screen","0",
               "-UseFeatures","".join(['1']*nfeats+['0']*(totfeats-nfeats))]
        return Popen(cmd, bufsize=-1)#, stdout=output)

class klustxml(object):
    """
    Class to retrieve metadata from klusters xml file
    """
    def __init__(self, xmlfile):
        from xml.etree import ElementTree
        self.tree = ElementTree.parse(xmlfile)
        self.version = self.tree.getroot().attrib['version']  # may not be correct
        self.chanbase = os.path.basename(xmlfile).split('_')[0]  # try to infer channel base

    @property
    def channels(self):
        """ List of tuples, containing the channels defined in each group. """
        # mspikes 2.0 backwards compatibility: channels don't have names but indices
        out = []
        for group in self.tree.iterfind('spikeDetection/channelGroups/group/channels'):
            names = tuple(name.text for name in group.findall('name')) or \
                tuple("%s_%d" % (self.chanbase, int(chan.text)+1) for chan in group.findall('channel'))
            out.append(names)
        return out

    @property
    def skipped(self):
        """ List of tuples, containing the entries skipped for each group """
        return [tuple(int(skt.text) for skt in group.findall("skipped/time")) \
                for group in self.tree.findall('spikeDetection/channelGroups/group')]

    @property
    def samplerate(self):
        return int(self.tree.find('acquisitionSystem/samplingRate').text)

    @property
    def ngroups(self):
        return len(self.tree.findall('spikeDetection/channelGroups/group'))

    def get_spike_times(self, group):
        """ Yield (channels,spike_times) tuples for all units in the group """
        from klustio import sort_unit
        fname = klustersite._fettemplate % (self.sitename, group)
        cname = klustersite._clutemplate % (self.sitename, group)
        channels = self.channels
        spikes = sort_unit(fname,cname)
        for i,times in enumerate(spikes):
            yield (channels[i], times)


def arrange_spikes(spike_times, spikes):
    """
    Reorganize spike times into numpy arrays.  The times are
    concatenated into a 1D array; the waveforms into a 2D array.
    Resorts the spikes so that the times are monotonically increasing.
    """
    from numpy import diff, concatenate
    spike_times = concatenate(spike_times)
    spikes = concatenate(spikes,axis=0)
    dt = diff(spike_times)
    if any(dt < 1):
        ind = spike_times.argsort()
        return spike_times[ind], spikes[ind,:]
    else:
        return spike_times, spikes

# Variables:
# End:
