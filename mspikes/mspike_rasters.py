# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""
A simple inspection tool for event data. Plots rasters from multiple
files with a common x axis.

Copyright (C) 2012 Daniel Meliza <dmeliza@dylan.uchicago.edu>
Created 2012-03-27
"""
import os, sys

figwidth = 5
figdpi = 80
tickspacing = 1
yskip = 1

def plot_rasters(toefiles, **kwargs):
    """
    Plot rasters. Loads data from files, figures out how many reps,
    and produces an appropriately sized figure.
    """
    from .events import plot_rasters as plotrast
    from arf.io.toelis import toefile
    from matplotlib.pyplot import figure

    tls = [toefile(fname).read()[0] for fname in toefiles if os.path.exists(fname)]

    # number of rasters in the plot
    ticksize = kwargs.get('ticksize',3)
    nlines = sum(len(tl) for tl in tls) + yskip * len(tls)
    plot_height = nlines * ticksize + tickspacing
    # need padding for tops and bottoms of plot

    fig = figure(figsize=(figwidth,plot_height/figdpi), dpi=figdpi)
    ax = fig.add_subplot(111)

    plotrast(*tls, ax=ax, labels=toefiles, yskip=yskip, markersize=ticksize)

    if 'xlim' in kwargs and kwargs['xlim'] is not None:
        ax.set_xlim(*kwargs['xlim'])
    else:
        ax.set_xlim(ax.xaxis.get_data_interval())

    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    return fig

def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('toefiles', metavar='toefile', nargs='+', help='toelis file to plot')
    parser.add_argument('-o', '--outfile', metavar='outfile', help='output plot file')
    parser.add_argument('-d',metavar='backend',dest='backend', help='specify matplotlib backend')
    parser.add_argument('-x','--xlim', type=float, nargs=2, metavar=('start','stop'),
                        help='set x axis limits (in ms)')
    parser.add_argument('-s','--ticksize',type=int, default=3, metavar='int',
                        help='set tick height')
    args = parser.parse_args(argv)

    if args.backend is not None:
        import matplotlib
        matplotlib.use(args.backend)

    fig = plot_rasters(**vars(args))
    if args.outfile is None:
        from matplotlib.pyplot import show
        show()
    else:
        fig.savefig(args.outfile)

if __name__=="__main__":
    sys.exit(main())


# Variables:
# End:
