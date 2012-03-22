# -*- coding: iso-8859-1 -*-
# -*- mode: python -*-

version = "2.2.0"

def lib_versions():
    import sys
    from arf import version as arfver
    from scipy import __version__ as spyver
    from numpy import __version__ as npyver
    return dict(mspikes = version,
                python = sys.version.split()[0],
                arf = arfver,
                numpy = npyver,
                scipy = spyver,)

__doc__ = """\
This is mspikes, a program for extracting spikes from extracellular recordings.

Version information:
%s

Copyright (C) 2011-2012 Dan Meliza <dan // meliza.org>
Project site: http://github.com/dmeliza/chirp
""" % ("\n".join("%-15s %s" % (k,v) for k,v in lib_versions().items()))


# Variables:
# End:
