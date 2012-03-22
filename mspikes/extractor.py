# -*- coding: iso-8859-1 -*-
"""
Extracts spikes from extracellular data.

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
_spike_resamp = 2 # NB: some values (e.g. 3) cause Klusters to crash horribly
_default_samplerate = 20000

class _dummy_writer(object):
    @staticmethod
    def write(message):
        pass
    @staticmethod
    def flush():
        pass

def extract_spikes(arfp, channel, thresh, maxrms=None, log=_dummy_writer, **kwargs):
    """
    Extract spike times and waveforms from all the entries in an arf
    file.

    arfp:           input file handle
    channel:        the channel to extract (name)
    thresh:         the threshold (in absolute or rms units)
    maxrms:         if defined, the maximum RMS allowed for an epoch;
                    if it exceeds this value it is skipped
    log:            if not None, output some status information here

    start:          if not None, exclude episodes starting before this time (in sec)
    stop:           if not None, exclude episodes starting after this time (in sec)
    abs_thresh:     if True, thresholding is absolute
    invert:         if True, invert signal prior to processing
    window:         the number of samples to extract on either side of the spike peak (def. 20)
    resamp:         resampling factor (def. 3)

    Yields:
    entry:            the current entry object
    spike times:      spike times, in units of (samples * resamp). E.g, if
                      data are sampled at 20 kHz and resampled 3x, a spike
                      occurring at 1 ms would have a time of 60.
    spike waveforms:  the waveforms for each spike, with dimension
                      nevents x window * resamp
    sampling rate:    sampling rate of waveform (and time units)

    If the entry is skipped (due to exceeding maxrms), the last three
    values in the yielded tuple are None

    The log stream is updated as the entries are processed.  Characters mean the following:
    . - normally processed
    S - skipped on the basis of time
    R - skipped on the basis of RMS
    N - skipped for lack of data
    """
    from spikes import spike_times, extract_spikes, signal_stats
    from numpy import fromiter

    window = kwargs.get('window',20)
    resamp = kwargs.get('resamp', _spike_resamp)
    absthresh = kwargs.get('abs_thresh',False)
    invert = kwargs.get('invert',False)
    start, stop = kwargs.get('start',None), kwargs.get('stop',None)

    log.write("** Channel %s: thresh=%3.2f (%s%s): " % (channel, thresh,
                                                        "abs" if absthresh else "rms",
                                                        ",invert" if invert else ""))
    spikecount = 0
    first_episode_time = min(e.attrs['timestamp'][0] for k,e in arfp.items())
    for ename,entry in arfp.items():
        log.flush()
        etime = entry.attrs['timestamp'] - first_episode_time
        if (start and etime < start) or (stop and etime > stop):
            log.write("S")
            yield entry, None, None, None
            continue

        try:
            data = entry.get_data(channel)
            Fs = entry[channel].attrs['sampling_rate']
        except (IndexError, KeyError):
            log.write("N")
            yield entry, None, None, None
            continue

        if invert:
            data *= -1
        if not absthresh or maxrms:
            mean,rms = signal_stats(data)

        if maxrms and rms > maxrms:
            log.write("R")
            yield entry, None, None, None
            continue

        if not absthresh:
            T = int(thresh * rms)
        else:
            T = thresh
        spike_t = spike_times(data, T, window).nonzero()[0]
        if spike_t.size > 0:
            spike_w = extract_spikes(data, spike_t, window, window)
            if resamp > 1:
                spike_w,shift = resample_and_align(spike_w, window, resamp)
                spike_t  = (spike_t * resamp) + shift
            log.write(".")
            spikecount += spike_t.size
            yield entry, spike_t, spike_w, Fs * resamp
        else:
            log.write("0")
    log.write(" %d events\n" % spikecount)

def resample_and_align(spikes, peak, resamp):
    """
    Resamples spike waveforms and aligns to peak values.

    spikes: spike waveforms, dimensions nevents x nsamples
    peak:   the expected location of the peak in the spikes (in samples)
    resamp: the resampling factor (integer; downsampling is highly discouraged)

    returns resampled and aligned spike waveforms, dimensions nevents x (nsamples-2)*resamp
            array of integers indicating how many samples each waveform was shifted (after resampling)

    raises an error if resamp <= 1
    """
    from numpy import zeros
    resamp = int(resamp)
    if resamp <= 1: raise ValueError, "Resampling factor must be > 1"
    nevents,nsamples = spikes.shape
    spikes = fftresample(spikes, nsamples * resamp)
    shift = find_peaks(spikes, peak * resamp, resamp)
    start = shift + resamp
    nshifted = (nsamples-2)*resamp
    shifted = zeros((nevents, nshifted))
    for i,spike in enumerate(spikes):
        shifted[i,:] = spike[start[i]:start[i]+nshifted]
    return shifted, shift

def find_peaks(spikes, peak, resamp):
    """
    Locate the peaks in an array of spikes.

    spikes: resampled spike waveforms, dimensions nevents x nsamples
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
