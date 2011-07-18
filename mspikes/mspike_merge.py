#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Merges toelis data from one or more cells into a single directory. This may be
necessary when the same unit gets recorded on multiple channels.

Usage: mspike_merge.py <cell1> <cell2> [<cell3> ...] <newcell>

The toelis data from <cell1>, ... are merged into new toelis files <newcell>_stim.
The old directories are renamed <cell1>_unmerged, so one of the old cell names
can be used for the merged data.  Toelis files are assumed to contain only one unit.
"""

import os, sys, glob
from arf.io.toelis import toefile, toelis
from extractor import __version__

def combine_toelis(*oldcelldirs):
    """
    Combine toelis data in multiple directories by stimulus name.
    Assumes the files are single-unit. Returns a dictionary keyed by
    stim name.
    """
    newtls = {}
    for celldir in oldcelldirs:
        pos = len(celldir) * 2 + 2  # position of stimulus name
        for tf in glob.iglob(os.path.join(celldir, '%s_*.toe_lis' % celldir)):
            tl = toefile(tf).read()[0]
            stim = tf[pos:-8]
            if newtls.has_key(stim):
                newtls[stim].extend(tl)
            else:
                newtls[stim] = tl
    return newtls

def main(argv=None):

    if argv is None: argv = sys.argv

    if len(argv) < 4:
        print __doc__
        return -1

    print "* Program: %s" % os.path.split(argv[0])[-1]
    print "* Version: %s" % __version__

    oldcells = [os.path.relpath(p) for p in argv[1:-1]]
    newcell = argv[-1]

    newtls = combine_toelis(*oldcells)

    if len(newtls) == 0:
        print "* Error: no valid toelis files found in any of the supplied directories"
        return -1

    # rename old directories
    for cell in oldcells:
        os.rename(cell, '%s_unmerged' % cell)
        print '* Moved %s to %s_unmerged' % (cell, cell)

    os.mkdir(newcell)
    for stim,tl in newtls.items():
        toefile(os.path.join(newcell, '%s_%s.toe_lis' % (newcell, stim))).write(tl)
    print "* Wrote %d toelis files to %s" % (len(newtls), newcell)

    return 0

if __name__=="__main__":
    sys.exit(main())

# Variables:
# End:
