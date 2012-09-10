# -*- coding: utf-8 -*-
# -*- mode: python -*-

version = "2.2.1b4"

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

Copyright (C) Dan Meliza, 2006-2012 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
""" % ("\n".join("%-15s %s" % (k,v) for k,v in lib_versions().items()))


# Variables:
# End:
