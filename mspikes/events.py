# -*- coding: iso-8859-1 -*-
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

def plot_rasters(*tls, **kwargs):
    """
    Plot one or more toelis objects as rasters with a common x axis.

    Optional arguments:

    tls:        the toelis objects to plot. Need to have .rasterize() method.
    ax:         axis to plot to. Default is to use gca()
    yoffset:    the starting y value for the first raster
    yskip:      the number of rows to skip between toelis objects
    labels:     text to insert above each set of rasters
    markersize: tick height (default 6)
    spacing:    tick spacing (overrides markersize if set)

    Tick size and spacing is controlled by two arguments, markersize
    (or ms) and spacing.  If spacing is not set, the markers have a
    fixed size and the spacing depends on the size of the axes.  If
    spacing is set, then the marker size is adjusted so that the
    spacing is as requested. It's a good idea to set the size of the
    axes based on the number of rasters.

    Additional keyword arguments are passed to ax.plot(). Some useful ones include:
    marker:     the marker to use (default is '|')
    markeredgewidth (or mew): width of the tick (default 0.5)

    Returns the axis object
    """
    from matplotlib.pyplot import gca, setp
    from itertools import izip

    ax = kwargs.pop('ax',gca())
    ystart = yoffset = kwargs.pop('yoffset',0)
    yskip = kwargs.pop('yskip',2)
    labels = kwargs.pop('labels',None)
    spacing = kwargs.pop('spacing',None)

    labely = []
    plots  = []
    hold   = ax.ishold()
    for i,tl in enumerate(tls):
        x,y = tl.rasterize()
        plots.append(ax.plot(x,y + yoffset,'k|',**kwargs)[0])
        yoffset += y.max() + 1 + yskip
        labely.append(yoffset - yskip)
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
    # adjust plot ylim to include tops and
    # bottoms of points; may be undefined behavior if there's
    # already stuff on the plot.
    corners_pix = ax.transAxes.transform([(0,0),(1,1)])
    corners_pix[:,1] += (-markersize, markersize)
    ylim = ax.transData.inverted().transform(corners_pix)[:,1]
    ax.set_ylim(*ylim)

    if labels:
        # not sure how b/c this fxn is
        trans = ax.get_yaxis_transform()
        for lbl,y in izip(labels,labely):
            ax.text(0.01, y, lbl, transform=trans, fontsize=markersize, va='bottom')

    return ax
# Variables:
# End:
