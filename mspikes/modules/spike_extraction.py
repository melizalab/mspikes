# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""spike detection and extraction

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Fri Jul 12 14:05:16 2013
"""
import numpy as nx

from mspikes import util
from mspikes.modules import dispatcher
from mspikes.types import Node, tag_set, DataBlock, DataError

@dispatcher.parallel('id', "samples", "scalar")
class spike_extract(Node):
    """Detect spike times in time series and extract waveforms

    Currently only works on individual channels, not groups.

    accepts: _samples (time series of extracellular voltage)
    emits:   _events (marked point process, time + waveform)
    passes:  all other tags

    """
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

    def __init__(self, name, **options):
        Node.__init__(self, name)
        util.set_option_attributes(self, options, thresh=None, interval=(1.5, 2.5))
        self.last_scalar = None # for scaling threshold
        self.reset()

    def reset(self):
        self.detector = None
        self.spike_queue = []
        self.last_chunk = None  # last chunk for spikes split across boundary

    def send(self, chunk):
        from fractions import Fraction
        from mspikes import register
        from mspikes.modules.spikes import detect_spikes
        from mspikes.util import repeatedly
        from itertools import chain
        from arf import DataTypes

        if "scalar" in chunk.tags:
            self.last_scalar = chunk
            return

        n_before, n_after = (util.to_samp_or_sec(x / 1000., chunk.ds) for x in self.interval)
        # reset the detector if there's a gap or ds changes
        if self.last_chunk is not None:
            last_sample_t = util.to_seconds(self.last_chunk.data.shape[0],
                                            self.last_chunk.ds, self.last_chunk.offset)
            gap = util.to_samp_or_sec(chunk.offset - last_sample_t, chunk.ds)
            if gap > 1 or self.last_chunk.ds != chunk.ds:
                self.reset()
        if self.detector is None:
            self.detector = detect_spikes(self.thresh, n_after)

        if self.last_scalar is not None:
            self.detector.scale_thresh(self.last_scalar.data.mean, self.last_scalar.data.rms)
        spike_it = chain(repeatedly(self.spike_queue.pop, 0),
                         ((t - n_before, t + n_after) for t in self.detector.send(chunk.data.astype('d'))))
        dt = nx.dtype([('start', nx.int32), ('spike', chunk.data.dtype, n_before + n_after)])
        spikes = nx.fromiter(self.get_spikes(chunk, spike_it), dt)
        self._log.debug("%s: %d spikes", chunk, spikes.size)
        if len(spikes):
            # spikes may have a negative time if they began in the previous
            # chunk, which is not handled well by arf_writer and other
            # downstream. Adjust offset and times so that times are >= 0
            adj = spikes[0]['start']
            if adj < 0:
                spikes['start'] -= adj
                offset = chunk.offset + Fraction(long(adj), chunk.ds)
            else:
                offset = chunk.offset
            new_id = chunk.id + "_spikes"
            if not register.has_id(new_id):
                register.add_id(new_id, uuid=None,
                                datatype=DataTypes.SPIKET,
                                source_dataset=chunk.id,
                                source_uuid=register.get_properties(chunk.id).get('uuid', None))

            Node.send(self, chunk._replace(id=chunk.id + "_spikes",
                                           data=spikes,
                                           offset=offset,
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

    @classmethod
    def options(cls, addopt_f, **defaults):
        # FIXME
        # addopt_f("--interval",
        #          help="interval around the spike peak to use (default=%(default)s)",
        #          type=float,
        #          default=(1.0, 2.0),
        #          nargs=2,
        #          metavar='MS')
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
        addopt_f("--nspikes",
                 help="maximum number of spikes to use in calculating PCs (default=%(default)d",
                 default=5000,
                 type=int,
                 metavar='INT')

    def __init__(self, name, **options):
        Node.__init__(self, name)
        util.set_option_attributes(self, options, interval=(1.0, 2.0), feats=3, raw=False,
                                   resample=3, nspikes=5000)
        self._queue = []

    def send(self, chunk):
        """ align spikes, compute features """
        # pass data we can't use
        if not arf.is_marked_pointproc(chunk.data) or "spike" not in chunk.data.dtype.names:
            Node.send(self, chunk)
        else:
            # need to read data now because it won't be available in close
            self._queue.append(chunk._replace(data=chunk.data[:]))
            if chunk.ds != self._queue[0].ds:
                self._queue.pop()
                raise DataError("%s: sampling rate doesn't match other spikes" % chunk)

    def close(self):
        if not self._queue:
            return
        times = [chunk.data['start'] + util.to_samp_or_sec(chunk.offset, chunk.ds) for
                 chunk in self._queue]
        spikes = [chunk.data['spike'] for chunk in self._queue]
        self._log.info("realigning spikes")
        times, spikes = realign_spikes(nx.concatenate(times),
                                       nx.concatenate(spikes),
                                       self.resample)
        features = [times, spikes]
        names = ['start', 'spike']

        if self.feats > 0:
            # TODO handle multiple channels
            self._log.info("calculating PCs")
            eigenvectors = get_eigenvectors(spikes, self.feats, self.nspikes)
            features.append(nx.dot(spikes, eigenvectors))
            names.append('PC')

        if self.raw:
            self._log.info("measuring spike features")
            for name, meas in measurements(spikes):
                features.append(meas)
                names.append(name)

        chunk = self._queue[0]
        self._log.debug("'%s': %d spikes", chunk.id, times.size)
        dt = nx.dtype([(n, a.dtype, a.shape[1] if a.ndim > 1 else 1)
                       for n, a in zip(names, features)])
        Node.send(self, DataBlock(id=chunk.id, offset=0, ds=chunk.ds * self.resample,
                                  data=nx.rec.fromarrays(features, dt), tags=chunk.tags))
        self._queue = []
        Node.close(self)


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
    return (times * upsample + start, shifted)


def find_peaks(spikes, peak, window):
    """Locate the peaks in an array of spikes.

    spikes: resampled spike waveforms, dimensions (nspikes, nsamples)
    peak:   the expected peak location
    window: the number of samples to either side of the peak to look for the peak

    Returns array of shift values relative to peak

    """
    r = slice(peak - window, peak + window + 1)
    return spikes[:,r].argmax(1) - window


def get_eigenvectors(spikes, nfeats, nspikes):
    """Calculate eigenvectors of spike waveforms

    spikes: resampled and aligned spike waveforms, dimensions (nspikes, nsamples)
    nfeats: the number of the most significant eigenvectors to return
    nspikes: the number of spikes to use

    Returns eigenvectors, dimension (nsamples, nfeats). Does not need to be
    transposed to calculate projections.

    The call to svd may "fail to converge", which just means dgesdd (a faster
    algorithm) didn't work. In this case, the algorithm tries to decompose the
    transpose. (see
    http://r.789695.n4.nabble.com/Observations-on-SVD-linpack-errors-and-a-workaround-td837282.html)

    """
    from numpy import dot
    from numpy.linalg import svd, LinAlgError
    # center data
    data = spikes[:nspikes] - spikes[:nspikes].mean(0)
    try:
        u, s, v = svd(data, full_matrices=0)
        return v[:nfeats].T.copy()
    except LinAlgError:
        u, s, v = svd(data.T, full_matrices=0)
        return u[:, :nfeats].copy()


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
