# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""
Functions for simple calculations with point process (i.e. time of
event) data.  Also includes some plotting tools.

Copyright (C) 2012 Dan Meliza <dmeliza@gmail.com>
Created 2012-04-11
"""

def rate(tl, time_range):
    """
    Calculate rate of events over an interval.

    tl:           toelis object
    time_range:   [start,stop) interval

    Returns a list of floats

    Note: to get an unnormalized count of events in a range, use the
    toelis.subrange() method.
    """
    tl = tl.subrange(*time_range)
    T  = 1. / (time_range[1] - time_range[0])
    return [T * len(x) for x in tl]


def intervals(tl):
    """ Calculate inter-event intervals. Returns a list of numpy arrays """
    from numpy import diff
    return [diff(x) for x in tl]


def histogram(tl, bins=20., time_range=None, **kwargs):
    """
    Count number of spikes in a series of evenly spaced bins.

    tl:          event time data (toelis object)
    bins:        if a scalar, the duration of each bin
                 if a sequence, defines bin edges
    time_range:  the time interval to calculate the histogram over.
                 Default is to use the min and max of tl.
    Additional arguments are passed to numpy.histogram

    Returns: array of counts (bins x trials), time bins

    Note: to average across trials, call mean(1) on returned counts array
    """
    from numpy import arange, histogram, zeros
    if isinstance(bins, (int,long,float)):
        if time_range is not None:
            onset,offset = time_range
        else:
            onset,offset = tl.range
        bins = arange(onset, offset + bins, bins)

    out = zeros((bins.size-1, len(tl)), dtype='i')
    for i,trial in enumerate(tl):
        out[:,i] = histogram(trial, bins=bins, **kwargs)[0]
    return out,bins


def phasic_index(tl, time_range=None):
    """
    Calculate phasic response index as reported by Gentner and Margoliash 2003.
    PR = \frac{D - \sum_i min(x_i,x_{i+1})}{D}

    where D is the duration of the analysis interval (typically
    defined by the start and stop of the stimulus) times the number of
    repetitions.

    time_range:  the time interval to do the analysis over. Default
                 is to use the min and max of tl
    """
    from numpy import diff, minimum, concatenate
    if time_range is None:
        time_range = tl.range
    else:
        tl = tl.subrange(*time_range)
    intervals = concatenate([diff(events) for events in tl])
    minsum = sum(minimum(intervals[:-1],intervals[1:]))
    stimdur = len(tl) * (time_range[1]-time_range[0])
    return (stimdur-minsum)/stimdur


def respstrength_var(tl, time_range=None):
    """
    Calculate variance of the firing rate using ISI distributions
    (i.e. the instantaneous firing rate).  This
    """
    pass


def plot_rasters(*tls, **kwargs):
    """
    Plot one or more toelis objects as rasters with a common x axis.

    Optional arguments:

    tls:        the toelis objects to plot. Need to have .rasterize() method.
    ax:         axis to plot to. Default is to use gca()
    yoffset:    the starting y value for the first raster
    yskip:      the number of rows to skip between toelis objects (default 2)
    labels:     sequence of strings to insert above each set of rasters
    markersize: tick height (default 6)
    spacing:    tick spacing (overrides markersize if set)
    labelsize:  size of label font (default 6)
    labelpos:   horizontal position of label relative to left axis (default 0.01)

    Tick size and spacing is controlled by two arguments, markersize
    (or ms) and spacing.  If spacing is not set, the markers have a
    fixed size and the spacing depends on the size of the axes.  If
    spacing is set, then the marker size is adjusted so that the
    spacing is as requested. It's a good idea to set the size of the
    axes based on the number of rasters.

    Additional keyword arguments are passed to ax.plot(). Some useful ones include:
    marker:     the marker to use (default is '|')
    markeredgewidth (or mew): width of the tick (default 0.5)

    Returns (plot objects, y offsets of gaps)
    """
    from matplotlib.pyplot import gca, setp
    from itertools import izip

    ax = kwargs.pop('ax',gca())
    ystart = yoffset = kwargs.pop('yoffset',0)
    yskip = kwargs.pop('yskip',2)
    labels = kwargs.pop('labels',None)
    spacing = kwargs.pop('spacing',None)
    labelsize = kwargs.pop('labelsize',6)
    labelpos = kwargs.pop('labelpos',0.01)

    labely = []
    plots  = []
    hold   = ax.ishold()
    for i,tl in enumerate(tls):
        x,y = tl.rasterize()
        plots.append(ax.plot(x,y + yoffset,'k|',**kwargs)[0])
        labely.append(max(yoffset - yskip/2, 0))
        yoffset += len(tl) + 1 + yskip
        ax.hold(True)
    ax.hold(hold)

    if spacing:
        # adjust marker size
        ylim = (ystart, yoffset - 1 - yskip)
        ylim_px = ax.transData.transform([(0,ylim[0]),(0,ylim[1])])[:,1]
        markersize = (ylim_px[1] - ylim_px[0]) / (ylim[1] - ylim[0] + 2) - spacing / 2.
        setp(plots,markersize=markersize)
    else:
        markersize = plots[0].get_markersize()

    # adjust label positions to align with bottoms of markers
    labely = [y - markersize/2 for y in labely]

    if labels is not None:
        # not sure how b/c this fxn is
        trans = ax.get_yaxis_transform()
        for lbl,y in izip(labels,labely):
            ax.text(labelpos, y, lbl, transform=trans, fontsize=labelsize, va='bottom')

    # adjust plot ylim to include tops and
    # bottoms of points; may be undefined behavior if there's
    # already stuff on the plot.
    ax.set_ylim(ax.yaxis.get_data_interval())
    corners_pix = ax.transAxes.transform([(0,0),(1,1)])
    corners_pix[:,1] += (-markersize, markersize)
    ylim = ax.transData.inverted().transform(corners_pix)[:,1]
    ax.set_ylim(*ylim)

    return plots,labely
# Variables:
# End:
