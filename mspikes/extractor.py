#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Extracts spikes from pcm_seq2 files
"""

import numpy as nx
import _pcmseqio
from utils import pcasvd, signalstats, filecache, fftresample
from scipy import weave


def sitestats(elog, channels=None, pen=None, site=None):
    """
    Calculates the first and second moments for each entry.
    Returns 2 NxP arrays, where N is the number of episodes
    and P is the number of channels; and a 1xN vector with
    the episode abstimes

    channels - restrict analysis to particular channels
    """
    oldsite = elog.site
    if pen!=None and site!=None:
        elog.site = (pen,site)
    files = elog.getfiles()
    files.sort(order=('abstime','channel'))

    # restrict to specified channels
    if channels!=None:
        ind = nx.asarray([(x in channels) for x in files['channel']])
        if ind.sum()==0:
            raise ValueError, "Channels argument does not specify any valid channels"
        files = files[ind]

    chanid = nx.unique(files['channel'])
    nchan = chanid.size
    chanidx = nx.zeros(chanid.max()+1,dtype='i')    # we know these are integers
    for ind,id in enumerate(chanid): chanidx[id] = ind
    
    neps = len(files) / nchan

    mu = nx.zeros((neps,nchan))
    rms = nx.zeros((neps,nchan))
    fcache = filecache()
    fcache.handler = _pcmseqio.pcmfile
    for i,file in enumerate(files):
        pfp = fcache[file['filebase']]
        pfp.entry = file['entry']
        stats = signalstats(pfp.read())
        col = chanidx[file['channel']]
        row = i / nchan
        mu[row,col] = stats[0]
        rms[row,col] = stats[1]

    elog.site = oldsite
    return mu, rms, nx.unique(files['abstime'])


def extract_spikes(S, events, **kwargs):
    """
    Extracts spike waveforms from raw signal data. For each
    offset in <events>, a window of samples around the event
    time is extracted.  Returns a 3D array, (sample, event, channel)

    Optional arguments:
    <window> - specify the (total) size of the spike window (default 30 ms)
    """

    window = kwargs.get('window',30)
    nsamples, nchans = S.shape
    nevents = len(events)
    spikes = nx.zeros((nevents, 2*window, nchans), S.dtype)

    for i in range(nevents):
        toe = events[i]
        if toe + window > nsamples or toe - window < 0: continue
        spikes[i,:,:] = S[toe-window:toe+window,:]

    return spikes


def get_projections(spikes, **kwargs):
    """
    Calculates the projections of the spikes onto the features
    Returns a 3D array, (events, dims, chans)

    spikes - 3D array, dimensions (events, values, channels)

    Optional Arguments:
    ndims - the number of principal components to use in calculating projections
            (default 3)    
    peaktrough - if true, include peak and trough calculations as features
    """

    nevents,nsamp,nchans = spikes.shape
    ndims = kwargs.get('ndims',3)

    if kwargs.get('peaktrough',True):
        nfeats = ndims + 3
    else:
        nfeats = ndims
        
    proj = nx.zeros((nevents,nchans,nfeats),'d')

    for i in range(nchans):
        proj[:,i,:ndims] = pcasvd(spikes[:,:,i], ndims)[0]

    if kwargs.get('peaktrough',True):
        # spikes should be aligned
        peak_ind = spikes[0,:,0].argmax()
        proj[:,:,ndims+0] = spikes[:,:,:].max(1)
        proj[:,:,ndims+1] = spikes[:,0:peak_ind,:].min(1)
        proj[:,:,ndims+2] = spikes[:,peak_ind:,:].min(1)

    return proj


def thresh_spikes(S, thresh, **kwargs):
    """
    Analyzes a signal matrix for threshold crossings. Whenever
    any one of the channels crosses its threshold, the peak of
    that signal is detected, and the time of the event is recorded.
    Returns the times of the events.

    <S> - the signal. Can be a vector or, for multiple channels,
          a matrix in which each column is a channel
    <thresh> - the crossing point(s) for the discriminator. Needs
               to be a 
    
    Optional arguments:
    <window> - the number of points to search ahead for the peak (in samples)
    <refrac> - the minimum distance between spikes (in samples)
    """

    window = kwargs.get('window',30)
    refrac = kwargs.get('refrac',window)

    if not isinstance(S, nx.ndarray):
        raise TypeError, "Input must be an ndarray"
    if S.ndim==1:
        S.shape = (S.size,1)
        
    nsamp, nchan = S.shape

    if nx.isscalar(thresh):
        thresh = nx.array([thresh] * nchan)
    elif not isinstance(thresh, nx.ndarray):
        raise TypeError, "Threshold must be a scalar or an array of values"
    elif thresh.ndim > 1 or thresh.size != nchan:
        raise ValueError, "Threshold array length must equal number of channels"

    events = []

    code = """
          #line 193 "extractor.py"
    
          for (int samp = 0; samp < nsamp; samp++) {
               for (int chan = 0; chan < nchan; chan++) {
                    if (S(samp, chan) > thresh(chan)) {
                         int   peak_ind = samp;
                         short peak_val = S(samp,chan);
                         for (int j = samp; j < samp + window; j++) {
                              if (S(j,chan) > peak_val) {
                                  peak_val = S(j,chan);
                                  peak_ind = j;
                              }
                         }
                         if (peak_ind > window && peak_ind + window < nsamp)
                              events.append(peak_ind);
                         samp = peak_ind + refrac - 1;
                         break;
                    }
                }
          }
    """
    weave.inline(code,['S','thresh','window','refrac','nchan','nsamp','events'],
                 type_converters=weave.converters.blitz)

    return nx.asarray(events)



def realign(spikes, **kwargs):
    """
    Realigns spike waveforms based on peak time. The peak of a linearly
    interpolated sample can be off by at least one sample, which
    has severe negative effects on later compression with PCA. Spike
    waveforms are upsampled before alignment.

    If the spikes are from more than one electrode, the mean across electrode
    is used to determine spike peak

    axis        = the axis to perform the analysis on (default 1)
    resamp_rate = integer indicating the upsampling factor (default 3)
    max_shift   = maximum amount peaks can be shifted (in samples, default 4)
    downsamp    = if true, the data are downsampled back to the original
                  sampling rate after peak realignment
    """
    
    ax = kwargs.get('axis',1)
    resamp_rate = kwargs.get('resamp_rate',3)
    max_shift = kwargs.get('max_shift',4) * resamp_rate

    np = spikes.shape[1] * resamp_rate
    upsamp = fftresample(spikes,np,axis=1)

    # now find peaks
    if upsamp.ndim>2:
        peaks = upsamp.mean(2).argmax(axis=ax)
    else:
        peaks  = upsamp.argmax(axis=ax)
    shift  = (peaks - nx.median(peaks)).astype('i')
    
    goodpeaks = nx.absolute(shift)<=(max_shift)
    nbadpeaks = shift.size - goodpeaks.sum()
    # this line will leave artefacts alone
    # shift[nx.absolute(shift)>(max_shift)] = 0
    # and this will remove spikes that can't be shifted
    if nbadpeaks > 0:
        print "Dropping %d unalignable trials" % nbadpeaks
        shift = shift[goodpeaks]
        upsamp = upsamp[goodpeaks,:,:]
    else:
        goodpeaks = None
    
    shape = list(upsamp.shape)
    start = -shift.min()
    stop  = upsamp.shape[1]-shift.max()
    shape[ax] = stop - start

    shifted = nx.zeros(shape, dtype=upsamp.dtype)
    for i in range(upsamp.shape[0]):
        d = upsamp[i,start+shift[i]:stop+shift[i]]
        shifted[i] = d

    if kwargs.get('downsamp',False):
        npoints = (stop - start) / resamp_rate
        dnsamp = fftresample(shifted, npoints, axis=1)
        return dnsamp,goodpeaks
    else:
        return shifted,goodpeaks
    
