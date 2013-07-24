# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""klusters format import and export

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jul 18 17:08:57 2013
"""

import logging
from collections import namedtuple

from mspikes import util
from mspikes.types import DataBlock, Node, Source, tag_set, MspikesError

# defines a klusters group
_group = namedtuple('_group', ('idx', 'spk', 'clu', 'fet', 'nfeats', 'nchannels', 'nsamples', 'peak_idx',
                               'float_scaling', 'sampling_rate'))


class KlustersError(MspikesError):
    """Raised for errors reading or writing klusters data"""
    pass


class klusters_writer(Node):
    """Export spike times and waveforms to klusters/klustakwik format

    accepts:  _events (marked point process, start=time, spike=waveform)
    emits:    none

    Outputs a number of files that can be used with Klusters or KlustaKwik.
     <basename>.spk.<g> - the spike file
     <basename>.fet.<g> - the feature file
     <basename>.clu.<g> - the cluster file (all spikes assigned to one cluster)
     <basename>.xml - the control file used by Klusters

    """
    _log = logging.getLogger("%s.spike_extract" % __name__)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("basename",
                 help="base name for output files (warning: overwrites existing files)",)
        addopt_f("--kkwik",
                 help="run KlustaKwik after writing files",
                 action='store_true')

    def __init__(self, basename, **options):
        util.set_option_attributes(self, options, kkwik=False)
        self._basename = basename
        self._groups = {}

    def send(self, chunk):
        """ write to clu/spk/fet files"""
        from numpy import savetxt
        data = chunk.data
        if "events" not in chunk.tags or data.dtype.names is None or "spike" not in data.dtype.names:
            return
        group = self._get_group(chunk)
        if group.sampling_rate != chunk.ds:
            self._log.warn("(id=%s, offset=%.2fs): sampling rate was %s, now %s",
                           chunk.id, float(chunk.offset), group.sampling_rate, chunk.ds)
        feats = int_features(chunk.data, group.float_scaling)
        if feats.shape[1] != group.nfeats:
            raise KlustersError("(id=%s, offset=%.2fs): feature count was %d, now %d" %
                                (chunk.id, float(chunk.offset), group.nfeats, feats.shape[1]))
        spks = int_spikes(chunk.data, group.float_scaling / 4)
        if spks.shape[1] != group.nsamples:     # TODO handle multiple channels
            raise KlustersError("(id=%s, offset=%.2fs): spike shape was %s, now %s" %
                                (chunk.id, float(chunk.offset), (group.nsamples, group.nchannels), spks.shape))
        savetxt(group.fet, feats, "%i")
        spks.tofile(group.spk)
        for j in xrange(feats.shape[0]):
            group.clu.write("1\n")

    def close(self):
        """ write xml file """
        if not self._groups:
            return
        srates = [g.sampling_rate for g in self._groups.itervalues()]
        sampling_rate = srates[0]
        if not all(s == sampling_rate for s in srates):
            self._log.war("sampling rate not the same for all channels: may lead to undefined behavior")
        xml = make_paramfile(self._groups, sampling_rate)
        self._log.info("writing parameters to %s.xml", self._basename)
        with open(self._basename + ".xml", "wt") as fp:
            fp.write(xml)
        # close open files
        kkwik_jobs = []
        for group in self._groups.itervalues():
            group.fet.close()
            group.spk.close()
            group.clu.close()
        if self.kkwik:
            run_klustakwik(self._basename, self._groups, self._log)
        self._groups = {}


    def throw(self, exception):
        """Turn off klustakwik option"""
        self.kkwik = False

    def _get_group(self, chunk):
        """ get handles for output files for a given id, creating as needed """
        try:
            return self._groups[chunk.id]
        except KeyError:
            idx = len(self._groups) + 1
            self._log.info("id '%s' will be stored in '%s.fet.%d'", chunk.id, self._basename, idx)
            spk = open("{0}.spk.{1}".format(self._basename, idx), "wb")
            clu = open("{0}.clu.{1}".format(self._basename, idx), "wt")
            clu.write("1\n")
            fet = open("{0}.fet.{1}".format(self._basename, idx), "wt")
            nfeats = count_features(chunk.data)
            fet.write("%d\n" % nfeats)
            group = _group(idx, spk, clu, fet, nfeats,
                           nsamples=chunk.data.dtype.fields['spike'][0].shape[0],
                           nchannels=1,              # TODO handle multiple channels
                           peak_idx=chunk.data['spike'].mean(0).argmax(),
                           float_scaling=get_scaling(chunk.data),
                           sampling_rate=chunk.ds)
            self._groups[chunk.id] = group
            return group


class klusters_reader(Source):
    """Import spike clusters from klusters format"""
    pass


def get_scaling(data):
    """Get the scaling factor for floating point features

    This is based on spike waveform range, with the idea that most
    features are going to reflect the peak-to-peak. The target range is
    ~32k. klusters (at least 1.6.4) reads to longs, so there's plenty of
    head room

    """
    rng = data['spike'].mean(0).ptp()  # TODO handle multiple channels
    return 32768 / rng


def count_features(data):
    """Count features in structured data array"""
    shapes = [(dt[0].shape or (1,)) for n, dt in data.dtype.fields.items() if n not in ("spike",)]
    return sum(s[0] for s in shapes)


def int_features(data, scaling):
    """Extract features from structured data as an array of integers

    scaling:  used to rescale floating point features to avoid quantization

    """
    from numpy import concatenate, dtype

    tgt_dtype = dtype('int64')
    fields = dict(data.dtype.fields)
    out = []
    # PCs come first
    if 'pcs' in fields:
        fields.pop('pcs')
        out.append((data['pcs'] * scaling).astype(tgt_dtype))

    for name, dtype in fields.iteritems():
        if name in ("start", "spike"):
            continue
        if dtype[0].kind=='f':
            out.append((data[name] * scaling).astype(tgt_dtype))
        elif dtype[0].kind=='i':
            out.append(data[name])
        else:
            raise KlustersError("data type {0} can't be converted to klusters feature".format(dtype[0]))

    # time comes last. it needs to be sampled
    out.append(data['start'].astype(tgt_dtype))

    # reshape to form single array
    for arr in out:
        if arr.ndim == 1:
            arr.shape = (arr.size,1)

    return concatenate(out, axis=1)


def int_spikes(data, scaling):
    """Rescale spikes and convert to 16-bit integers.

    This data is only for display purposes in klusters, so it's okay if a few
    outliers clip (but not overflow)

    """
    from numpy import minimum, maximum, dtype
    tgt_dtype = dtype('int16')
    intmax = 2 ** (tgt_dtype.itemsize * 8 - 1)
    # may be slow
    spikes = maximum(minimum(data['spike'] * scaling, intmax - 1), -intmax)
    return spikes.astype(tgt_dtype)


def make_paramfile(groups, sampling_rate, sample_bits=16):
    """Generate the klusters parameter file. Returns an xml string"""
    from xml.etree import ElementTree as et
    from mspikes import __version__

    root = et.Element('parameters', creator='mspikes', version=__version__)
    acq = et.SubElement(root, "acquisitionSystem")
    text_element(acq, 'nBits', sample_bits)
    # TODO multiple channels per group
    text_element(acq, 'nChannels', len(groups))
    text_element(acq, 'samplingRate', sampling_rate)
    text_element(acq, 'voltageRange', 20)
    text_element(acq, 'amplification', 1000)
    text_element(acq, 'offset', 0)
    text_element(et.SubElement(root, 'fieldPotentials'), 'lfpSamplingRate', 1250)

    sd = et.SubElement(root, 'spikeDetection')
    cg = et.SubElement(sd, 'channelGroups')
    for i, name in enumerate(sorted(groups, key=natsorted)):
        group = groups[name]
        # TODO multiple channels per group
        g = et.SubElement(cg, "group")
        c = et.SubElement(g, "channels")
        text_element(c, "channel", i)
        text_element(c, "name", name)
        text_element(g, "nSamples", group.nsamples)
        text_element(g, "peakSampleIndex", group.peak_idx)
        text_element(g, "nFeatures", group.nfeats)

    return et.tostring(root)


def run_klustakwik(basename, groups, log):
    """Run klustakwik on groups, if it exists"""
    from subprocess import Popen
    cmd = "KlustaKwik %s %d -Screen 0 -UseFeatures %s"
    try:
        jobs = [Popen(cmd % (basename, g.idx, "1" * (g.nfeats - 1) + "0"), bufsize=-1) for
                i, g in enumerate(groups)]
    except OSError:
        log.warning("unable to run KlustaKwik - is it installed?")
        return

    for i, job in enumerate(jobs):
        log.info("waiting for KlustaKwik job %d to finish...", i + 1)
        job.wait()



def text_element(parent, tag, value, **attribs):
    """Create a text sub-element"""
    from xml.etree import ElementTree as et
    el = et.SubElement(parent, tag, **attribs)
    el.text = str(value)
    return el


def natsorted(key):
    """ key function for natural sorting. usage: sorted(seq, key=natsorted) """
    import re
    return map(lambda t: int(t) if t.isdigit() else t, re.split(r"([0-9]+)",key))



# Variables:
# End:



