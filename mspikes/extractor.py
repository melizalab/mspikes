#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Extracts spikes from extracellular data.

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""

def extract_spikes(arfp, channel, thresh, **kwargs):
    """
    Extract spike times and waveforms from all the entries in an arf
    file.

    arfp:           input file handle
    channel:        the channel to extract
    thresh:         the threshold (in absolute or rms units)
    abs_thresh:     if True, thresholding is absolute
    window:         the number of samples per spike (def. 20)
    resamp:         resampling factor (def. 3)
    refrac:         the min. number of samples between peak and
                    next threshold crossing (def. window)

    Yields (for each entry):
    spike times:      spike times
    spike waveforms:  the waveforms for each spike, with dimension
                      nevents x window * resamp
    """
    from numpy import where
    from spikes import spike_times, extract_spikes, signal_stats

    window = kwargs.get('window',20)
    resamp = kwargs.get('resamp', 3)
    refrac = kwargs.get('refrac',window)
    absthresh = kwargs.get('abs_thresh',False)

    for entry in arfp:
        data,Fs = entry.get_data(channel)
        if not absthresh:
            mean,rms = signal_stats(data)
            T = int(thresh / rms)
        else:
            T = thresh
        spike_t = spike_times(data, T, window, refrac).nonzero()[0]
        spike_w = extract_spikes(data, spike_t, window)
        if resamp > 1:
            spike_w  = fftresample(spike_w, window * resamp * 2)
            spike_t += find_peaks(spike_w, window * resamp, resamp)
        yield 1./ Fs * spike_t, spike_w


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


def projections(spikes, nfeats=3):
    """
    Calculate projections of spikes on principal components.

    spikes:  resampled and aligned spike waveforms, nevents x nsamples
    nfeats:  the number of PCs to use.

    Returns:
    projections on to first nfeats PCs, dimension nevents x nfeats
    """
    from scipy.linalg import svd, get_blas_funcs
    nevents,nsamples = spikes.shape
    gemm,= get_blas_funcs(('gemm',),(spikes,spikes))

    data = spikes - spikes.mean(0)
    u,s,v = svd(data, full_matrices=0)
    v = v[:nfeats,:]
    return gemm(1.0, data, v, trans_b=1), v


def measurements(spikes, features=('height','trough1','trough2','ptt','peakw','troughw')):
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
    Returns:   nevents x nfeats array
    """
    from numpy import column_stack, asarray
    nevents, nsamples = spikes.shape
    peak_ind = nsamples/2
    out = []
    for f in features:
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
    return column_stack(out)


def realign(spikes, resamp):
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
