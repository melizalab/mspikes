#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- mode: python -*-
"""
Klusters/Klustakwik data are spread across several files, with
metadata stored in an xml file.  This module contains a class for
managing a collection of klusters data for a single site, and some
utility functions.

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
from collections import defaultdict

class klustersite(object):
    """
    Klusters data are organized into the following files:

    <base>.xml - the parameters file, describes which channels
                 are in which groups
    For each group <g>:
    <base>.spk.<g> - the spike file: 16-bit samples
    <base>.fet.<g> - the feature file
    <base>.clu.<g> - the cluster file (all spikes assigned to one cluster)

    Usage:
    >>> with klustersite(basename,channels=((0,1),2),thresh=(4.5,4.5,4.5),nfeats=3,window=20) as ks:
    >>>     ks.addevents(spikes, features)
    >>>     ks.group += 1
    >>>     ks.addevents(spikes, features)
    """
    _spktemplate = "%s.spk.%d"
    _clutemplate = "%s.clu.%d"
    _fettemplate = "%s.fet.%d"

    def __init__(self, sitename, **kwargs):
        """
        Initialize a klusters site.

        sitename:   the basename for the files
        channels:   sequence of channel groups, which can be single
                    channels or sequences of channels
        thresh:     the threshold used to extract spikes
        nfeats:     the number of PCA features per channel
        measurements:  the raw feature measurements
        window:     the number of samples per spike (automatically adjusted for resampling)
        sampling_rate:  the base sampling rate of the data (default 20000)
        resamp:         resampling factor for the spikes
        """
        self.sitename = sitename
        self.groups = tuple((x if hasattr(x,'__len__') else (x,) for x in kwargs['channels']))
        self.nsamples = 2 * kwargs['window'] * kwargs['resamp'] - kwargs['resamp'] * 2
        self.nfeatures = tuple((kwargs['nfeats'] + len(kwargs['measurements'])) * len(c) + 1 for c in self.groups)
        self.nkfeats = tuple((kwargs['nfeats'] * len(c)) for c in self.groups)
        self.thresh = kwargs['thresholds']
        self.samplerate = kwargs['sampling_rate'] * kwargs['resamp']
        self.skipped = [[] for x in self.groups]

        self.spk = defaultdict(self._openspikefile)
        self.clu = defaultdict(self._openclufile)
        self.fet = defaultdict(self._openfetfile)

        self.group = 0

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.writexml()
        for v in self.spk.values(): v.close()
        for v in self.clu.values(): v.close()
        for v in self.fet.values(): v.close()

    @property
    def spikefile(self):
        return self._spktemplate % (self.sitename, self.group + 1)

    @property
    def clufile(self):
        return self._clutemplate  % (self.sitename, self.group + 1)

    @property
    def fetfile(self):
        return self._fettemplate % (self.sitename, self.group + 1)

    def _openspikefile(self):
        """ Open handle to spike file """
        return open(self.spikefile,'wb')

    def _openclufile(self):
        fp = open(self.clufile,'wt')
        fp.write("1\n")
        return fp

    def _openfetfile(self):
        fp = open(self.fetfile,'wt')
        fp.write("%d\n" % self.nfeatures[self.group])
        return fp

    def writexml(self):
        """  Generate the xml file for the site """
        total_channels = sum(len(x) for x in self.groups)
        with open(self.sitename + ".xml", 'wt') as fp:
            fp.writelines(('<parameters creator="mspikes" version="2.0" >\n',
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

            for i,channelgroup in enumerate(self.groups):
                if isinstance(channelgroup, int):
                    channelgroup = (channelgroup,)

                fp.write("   <group>\n    <channels>\n")
                for j,chan in enumerate(channelgroup):
                    fp.write("     <channel>%d</channel>\n" % chan)
                    fp.write("     <thresh>%3.2f</thresh>\n" % self.thresh[j])
                fp.write("    </channels>\n")
                fp.write("    <nSamples>%d</nSamples>\n" % self.nsamples)
                fp.write("    <peakSampleIndex>%d</peakSampleIndex>\n" % (self.nsamples/2))

                fp.write("    <nFeatures>%d</nFeatures>\n" % (self.nfeatures[i] - 1))
                fp.write("    <skipped>\n    ")
                for etime in self.skipped[i]:
                    fp.write("<time>%d</time>" % etime)
                fp.write("\n    </skipped>\n")
                fp.write("   </group>\n")
            fp.write("  </channelGroups>\n </spikeDetection>\n</parameters>\n")

    def addevents(self, spikes, features):
        """
        Write events to the spk/clu/fet files in the current group.
        Can be called more than once, although typically this is not
        very useful because realignment and PCA require all the spikes
        to be in memory.

        spikes: ndarray, nevents by nchannels by nsamples
                (or nevents by nsamples for 1 chan)
        features: ndarray, nevents by nfeatures
        """
        from numpy import savetxt
        assert spikes.shape[0] == features.shape[0], "Number of events in arguments don't match"
        assert features.shape[1] == self.nfeatures[self.group], \
               "Group %d should have %d features, got %d" % (self.group, self.nfeatures[self.group], features.shape[1])
        spikes.astype('int16').tofile(self.spk[self.group])
        savetxt(self.fet[self.group], features, "%i")
        fp = self.clu[self.group]
        for j in xrange(features.shape[0]): fp.write("1\n")

    def skipepochs(self, *epochs):
        """
        Mark one or more recording epochs as skipped; this information
        can be used later to determine if the absence of any spike
        times for an epoch is due to the epoch being skipped or not.

        epochs: a list of IDs for the epochs that were skipped
        """
        self.skipped[self.group].extend(epochs)

    def run_klustakwik(self):
        """ Runs KlustaKwik on the current group """
        from subprocess import Popen
        nfeats = self.nkfeats[self.group]
        totfeats = self.nfeatures[self.group]
        self.fet[self.group].close()
        self.clu[self.group].close()
        cmd = ["KlustaKwik",self.sitename,str(self.group+1),
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

    @property
    def channels(self):
        """ List of tuples, containing the channels defined in each group. """
        return [tuple(int(channel.text) for channel in group.findall('channel')) \
                for group in self.tree.findall('spikeDetection/channelGroups/group/channels')]

    @property
    def skipped(self):
        """ List of tuples, containing the entries skipped for each group """
        return [tuple(int(skt.text) for skt in group.findall("skipped/time")) \
                for group in self.tree.findall('spikeDetection/channelGroups/group/')]

    @property
    def samplingrate(self):
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


def check_times(spike_times):
    """ Assert that the spike times are monotonically increasing """
    from numpy import diff
    dt = diff(spike_times)
    if any(dt < 1):
        raise ValueError, "Spike times are not monotonic! (%s)" % dt.nonzero()[0]

# Variables:
# indent-tabs-mode: t
# End:
