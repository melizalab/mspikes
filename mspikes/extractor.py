#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Extracts spikes from extracellular data.

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
__version__ = "2.0a1"
_spike_resamp = 2 # NB: some values (e.g. 3) cause Klusters to crash horribly
_default_samplerate = 20000

def extract_spikes(arfp, channel, thresh, maxrms=None, log=None, **kwargs):
    """
    Extract spike times and waveforms from all the entries in an arf
    file.

    arfp:           input file handle
    channel:        the channel to extract
    thresh:         the threshold (in absolute or rms units)
    maxrms:         if defined, the maximum RMS allowed for an epoch;
                    if it exceeds this value it is skipped
    log:            if not None, output some status information here

    abs_thresh:     if True, thresholding is absolute
    inverted:       if True, or if (channel in inverted), invert signal prior to processing
    window:         the number of samples per spike (def. 20)
    resamp:         resampling factor (def. 3)
    refrac:         the min. number of samples between peak and
                    next threshold crossing (def. window)

    Yields:
    entry:            the current entry object
    spike times:      spike times, in units of (samples * resamp). E.g, if
                      data are sampled at 20 kHz and resampled 3x, a spike
                      occurring at 1 ms would have a time of 60.
    spike waveforms:  the waveforms for each spike, with dimension
                      nevents x window * resamp
    sampling rate:    sampling rate of waveform (and time units)
    """
    from numpy import where
    from spikes import spike_times, extract_spikes, signal_stats

    window = kwargs.get('window',20)
    resamp = kwargs.get('resamp', _spike_resamp)
    refrac = kwargs.get('refrac',window)
    absthresh = kwargs.get('abs_thresh',False)
    invert = kwargs.get('inverted',[])

    if log: log.write("Extracting spikes from channel %d at thresh %3.2f (%s) " % \
                      (channel, thresh, "abs" if absthresh else "rms"))
    spikecount = 0
    for entry in arfp:
        data,Fs = entry.get_data(channel)
        if invert or channel in invert:
            data *= -1
        if not absthresh or maxrms:
            mean,rms = signal_stats(data)

        if maxrms and rms > maxrms:
            if log:
                log.write("S")
                log.flush()
            continue

        if not absthresh:
            T = int(thresh * rms)
        else:
            T = thresh
        spike_t = spike_times(data, T, window, refrac).nonzero()[0]
        spike_w = extract_spikes(data, spike_t, window)
        if resamp > 1:
            spike_w  = fftresample(spike_w, window * resamp * 2)
            spike_t  *= resamp
            spike_t  += find_peaks(spike_w, window * resamp, resamp)
        if log:
            log.write(".")
            log.flush()
        spikecount += spike_t.size
        yield entry, spike_t, spike_w, Fs * resamp
    if log: log.write(" %d events\n" % spikecount)


def find_peaks(spikes, peak, resamp):
    """
    Locate the peaks in an array of spikes.

    spikes: resampled spike waveforms, dimensions nevents x window * 2
    peak:   the expected peak location
    resamp: the resampling factor

    Returns: array of shift values
    """
    r = slice(peak-resamp,peak+resamp+1)
    return spikes[:,r].argmax(1) - resamp


def projections(spikes, **kwargs):
    """
    Calculate projections of spikes on principal components.

    spikes:  resampled and aligned spike waveforms, nevents x nsamples
    nfeats:  the number of PCs to use.

    Returns:
    projections on to first nfeats PCs, dimension nevents x nfeats
    """
    from scipy.linalg import svd, get_blas_funcs
    nfeats = kwargs.get('nfeats')
    nevents,nsamples = spikes.shape
    gemm,= get_blas_funcs(('gemm',),(spikes,spikes))

    data = spikes - spikes.mean(0)
    u,s,v = svd(data, full_matrices=0)
    v = v[:nfeats,:]
    return gemm(1.0, data, v, trans_b=1), v

_default_measurements = ('height','trough1','trough2','ptt','peakw','troughw')

def measurements(spikes, **kwargs):
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
    measurements: sequence of features to measure

    Returns:   nevents x nfeats array
    """
    from numpy import column_stack, asarray
    nevents, nsamples = spikes.shape
    peak_ind = nsamples/2
    out = []
    for f in kwargs.get('measurements'):
        if f == 'height':
            out.append(spikes.max(1))
        elif f == 'trough1':
            out.append(spikes[:,:peak_ind].min(1))
        elif f == 'trough2':
            out.append(spikes[:,peak_ind:].min(1))
        elif f == 'ptt':
            out.append(spikes[:,peak_ind:].argmin(1))
        elif f == 'peakw':
            val = [(spike >= spike.max()/2).sum() for spike in spikes]
            out.append(asarray(val))
        elif f == 'troughw':
            val = [(spike[peak_ind:] <= spike[peak_ind:].min()/2).sum() for spike in spikes]
            out.append(asarray(val))
    if out:
        return column_stack(out)
    else:
        return None


def align_spikes(spikes, **kwargs):
    """
    Realigns spike waveforms based on peak time.

    spikes:     nevents x nsamples array of spike waveforms. should be
                upsampled prior to calling this function. Peaks are assumed
                to be in the middle of the window (nsamples / 2)
    resamp:     the resampling rate. in theory, spikes should not be misaligned
                more than this amount.

    Returns:
    array of resampled spikes, dimensions nevents x
    (nsamples-resamp*2). To ensure consistency, the same number of
    samples are removed from each end regardless of whether the spike
    was shifted or not.
    """
    from numpy import zeros
    resamp = kwargs.get('resamp')
    nevents,nsamples = spikes.shape
    start = find_peaks(spikes, nsamples / 2, resamp) + resamp
    nshifted = nsamples - resamp*2
    shifted = zeros((nevents, nshifted), dtype=spikes.dtype)
    for i,spike in enumerate(spikes):
        shifted[i,:] = spike[start[i]:start[i]+nshifted]
    return shifted


def fftresample(S, npoints, axis=1):
    """
    Resample a signal using discrete fourier transform. The signal
    is transformed in the fourier domain and then padded or truncated
    to the correct sampling frequency.  This should be equivalent to
    a sinc resampling.
    """
    from scipy.fftpack import rfft, irfft
    Sf = rfft(S, axis=axis)
    return (1. * npoints / S.shape[axis]) * irfft(Sf, npoints, axis=axis, overwrite_x=1)


# Variables:
# End:
