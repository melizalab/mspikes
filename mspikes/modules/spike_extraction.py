# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""spike detection and extraction

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Fri Jul 12 14:05:16 2013
"""
import logging
import numpy as nx

from mspikes import util
from mspikes.modules import dispatcher
from mspikes.types import Node, tag_set

@dispatcher.parallel('id', "samples")
class spike_extract(Node):
    """Detect spike times in time series and extract waveforms

    Currently only works on individual channels, not groups.

    accepts: _samples (time series of extracellular voltage)
    emits:   _events (marked point process, time + waveform)
    passes:  all other tags

    """
    _log = logging.getLogger("%s.spike_extract" % __name__)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--thresh",
                 help="detection threshold (negative values imply negative-going crossings)",
                 type=float,
                 required=True,
                 metavar='FLOAT')
        addopt_f("--interval",
                 help="the interval around the peak to extract (default=%(default)s)",
                 type=float,
                 default=(1.5, 2.5),
                 nargs=2,
                 metavar='MS')

    def __init__(self, **options):
        util.set_option_attributes(self, options, thresh=None, interval=(1.5, 2.5))
        self.reset()

    def reset(self):
        self.detector = None
        self.spike_queue = []
        self.last_chunk = None  # store last chunk in case spike splits across boundary

    def send(self, chunk):
        from mspikes.modules.spikes import detect_spikes
        from mspikes.util import repeatedly
        from itertools import chain

        n_before, n_after = (util.to_samples(x / 1000., chunk.ds) for x in self.interval)
        # reset the detector if there's a gap or ds changes
        if self.last_chunk is not None:
            last_sample_t = util.to_seconds(self.last_chunk.data.size, self.last_chunk.ds, self.last_chunk.offset)
            gap = util.to_samples(chunk.offset - last_sample_t, chunk.ds)
            if gap > 1 or self.last_chunk.ds != chunk.ds:
                self.reset()
        if self.detector is None:
            self.detector = detect_spikes(self.thresh, util.to_samples(self.interval[1], chunk.ds))

        spike_it = chain(repeatedly(self.spike_queue.pop, 0),
                         ((t - n_before, t + n_after) for t in self.detector.send(chunk.data)))
        dt = nx.dtype([('start', nx.int32), ('spike', chunk.data.dtype, n_before + n_after)])
        spikes = nx.fromiter(self.get_spikes(chunk, spike_it), dt)

        if len(spikes):
            Node.send(self, chunk._replace(id=chunk.id + "_spikes",
                                           data=nx.fromiter(spikes, dtype=dt),
                                           tags=tag_set("events")))
        self.last_chunk = chunk

    def get_spikes(self, chunk, times):
        data = chunk.data
        nsamples = data.shape[0]
        for start, stop in times:
            if stop > nsamples:
                # queue the spike until the next data chunk arrives
                self.spike_queue.append((start - nsamples, stop - nsamples))
                continue
            if start < 0:
                if self.last_chunk is not None:
                    spk = nx.concatenate((self.last_chunk.data[slice(start, None)], data[slice(0, stop)]))
                else:
                    continue
            else:
                spk = data[start:stop]

            yield (start, spk)


@dispatcher.parallel('id', "events")
class spike_features(Node):
    """Calculate spike features using PCA and raw measurements

    accepts:  _events (marked point process, start=time, spike=waveform)
    emits:    _events (marked point process, start=time, spike=waveform, pc1=array, pc2=array, ...)
    passes:   all other tags

    """
    _log = logging.getLogger("%s.spike_features" % __name__)

    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("--interval",
                 help="interval around the spike peak to use (default=%(default)s)",
                 type=float,
                 default=(1.0, 2.0),
                 nargs=2,
                 metavar='MS')
        addopt_f("--feats",
                 help="include %(metavar)s features from PCA (default=%(default)d)",
                 default=3,
                 type=int,
                 metavar='INT')
        addopt_f("--raw",
                 help="include raw spike measurements as features",
                 action='store_true')
        addopt_f("--resample",
                 help="factor to upsample spikes for alignment (default=%(default)d)",
                 default=3,
                 type=int,
                 metavar='INT')
        addopt_f("--spikes",
                 help="accumulate %(metavar)s spikes before calculating statistics (default=%(default)d)",
                 default=1000,
                 type=int,
                 metavar='INT')

    def __init__(self, **options):
        util.set_option_attributes(self, options, interval=(1.0, 2.0), feats=3, raw=False,
                                   resample=3, spikes=1000)
        self._eigenvectors = None
        self._reset_queue()

    def _reset_queue(self):
        self._times = []
        self._spikes = []
        self._nspikes = 0


    def send(self, chunk):
        """ align spikes, compute features """

        # pass data we can't use
        data = chunk.data
        if data.dtype.names is None or "spike" not in data.dtype.names:
            Node.send(self, chunk)
            return

        self._times.append(data['start'] + util.to_samples(chunk.offset, chunk.ds))
        self._spikes.append(data['spike'])
        self._nspikes += data.shape[0]

        if self._nspikes < self.spikes:
            return

        times = nx.concatenate(self._times)
        spikes = nx.concatenate(self._spikes)
        self._reset_queue()

        times, spikes = realign_spikes(times, spikes, self.resample)
        features = [times, spikes]
        names = ['start', 'spike']

        if self.feats > 0:
            # TODO handle multiple channels
            if self._eigenvectors is None:
                self._eigenvectors = get_eigenvectors(spikes, self.feats)
            features.append(nx.dot(spikes, self._eigenvectors))
            names.append('PC')

        if self.raw:
            for name, meas in measurements(spikes):
                features.append(meas)
                names.append(name)

        dt = nx.dtype([(n, a.dtype, a.shape[1] if a.ndim > 1 else 1) for n, a in zip(names, features)])
        Node.send(self, chunk._replace(ds=chunk.ds * self.resample, data=nx.rec.fromarrays(features, dt)))


def realign_spikes(times, spikes, upsample):
    """Realign spikes to their peaks using bandwidth-limited resampling

    times : one-dimensional array of spike times, in units of samples
    spikes : array of spike waveforms, with dimensions (nspikes, npoints)
    upsample : integer, the factor by which to upsample the data for realignment

    Returns (times, spikes), with the sampling rate increased by a factor of upsample

    """
    upsample = int(upsample)
    assert upsample > 1, "Upsampling factor must be greater than 1"
    nevents, nsamples = spikes.shape

    # first infer the expected peak time
    expected_peak = spikes.mean(0).argmax() * upsample
    spikes = fftresample(spikes, nsamples * upsample)
    # find peaks within upsample samples of mean peak
    shift = find_peaks(spikes, expected_peak, upsample)
    start = shift + upsample
    nshifted = (nsamples - 2) * upsample
    shifted = nx.zeros((nevents, nshifted))
    for i,spike in enumerate(spikes):
	shifted[i,:] = spike[start[i]:start[i]+nshifted]
    return (times * upsample + shift, shifted)


def find_peaks(spikes, peak, window):
    """Locate the peaks in an array of spikes.

    spikes: resampled spike waveforms, dimensions (nspikes, nsamples)
    peak:   the expected peak location
    window: the number of samples to either side of the peak to look for the peak

    Returns array of shift values relative to peak

    """
    r = slice(peak - window, peak + window + 1)
    return spikes[:,r].argmax(1) - window


def get_eigenvectors(spikes, nfeats):
    """Calculate eigenvectors of spike waveforms

    spikes: resampled and aligned spike waveforms, dimensions (nspikes, nsamples)
    nfeats: the number of the most significant eigenvectors to return

    Returns eigenvectors, dimension (nsamples, nfeats). Does not need to be
    transposed to calculate projections.

    """
    from numpy.linalg import svd
    u, s, v = svd(spikes - spikes.mean(0), full_matrices=0)
    return v[:nfeats, :].T.copy()


def measurements(spikes):
    """
    Makes the following measurements on spike shape:
    height -   max value of trace
    trough1 -  min value of trace before peak
    trough2 -  min value of trace after peak
    ptt     -  peak to trough2 time (in samples)
    peakw   -  peak width (in samples) at half-height
    troughw -  trough2 width (in samples) at half-depth
    ...

    spikes:    resampled, aligned spike waveforms, nevents x nsamples
    Returns:   dict of arrays, dimension (nevents,), keyed by measurement type
    """
    from numpy import asarray
    nevents, nsamples = spikes.shape
    peak_ind = spikes.mean(0).argmax()
    return (('height', spikes.max(1)),
            ('trough1', spikes[:, :peak_ind].min(1)),
            ('trough2', spikes[:, peak_ind:].min(1)),
            ('ptt', spikes[:, peak_ind:].argmin(1)),
            ('peakw', asarray([(spike >= spike.max()/2).sum() for spike in spikes])),
            ('troughw', asarray([(spike[peak_ind:] <= spike[peak_ind:].min()/2).sum() for spike in spikes])))


def fftresample(S, npoints, axis=1):
    """
    Resample a signal using discrete fourier transform. The signal
    is transformed in the fourier domain and then padded or truncated
    to the correct sampling frequency.  This should be equivalent to
    a sinc resampling.
    """
    from numpy.fft import rfft, irfft
    Sf = rfft(S, axis=axis)
    return (1. * npoints / S.shape[axis]) * irfft(Sf, npoints, axis=axis)



# Variables:
# End:
