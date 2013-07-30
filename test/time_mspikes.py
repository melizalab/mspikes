# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""profile toolchain run

time_mspikes.py <profile> OPTIONS

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Mon Jul 29 18:04:28 2013
"""

import sys
import cProfile
from mspikes import main

if __name__=="__main__":

    if len(sys.argv) < 3:
        print __doc__
        sys.exit(-1)

    print "saving profile in", sys.argv[1]
    cProfile.run("main.mspikes(sys.argv[2:])", sys.argv[1])


# Variables:
# End:
