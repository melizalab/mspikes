# -*- coding: utf-8 -*-
# -*- mode: python -*-
import sys

if sys.hexversion < 0x02070000:
    raise RuntimeError("Python 2.7 or higher required")

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import find_packages

from numpy.distutils.core import setup, Extension


VERSION = '3.0.0-SNAPSHOT'
cls_txt = """
Development Status :: 5 - Production/Stable
Intended Audience :: Science/Research
License :: OSI Approved :: GNU General Public License (GPL)
Programming Language :: Python
Topic :: Scientific/Engineering
Operating System :: Unix
Operating System :: POSIX :: Linux
Operating System :: MacOS :: MacOS X
Natural Language :: English
"""
short_desc = "Processing framework for time series and point process data"
long_desc = """
FIXME
"""

# _readklu = Extension('klustio', sources=['src/klustio.cc'])
# _spikes = Extension('spikes', sources=['src/spikes.pyf', 'src/spikes.c'])

setup(name="mspikes",
      version=VERSION,
      description=short_desc,
      long_description=long_desc,
      classifiers=[x for x in cls_txt.split("\n") if x],
      author='C Daniel Meliza',
      author_email='"dan" at the domain "meliza.org"',
      maintainer='C Daniel Meliza',
      maintainer_email='"dan" at the domain "meliza.org"',
      packages=find_packages(),
      entry_points={'console_scripts':
                    ['mspikes=mspikes.main:mspikes']},
      #               ['mspike_extract=mspikes.mspike_extract:main',
      #                'mspike_group=mspikes.mspike_group:main',
      #                'mspike_view=mspikes.mspike_view:main',
      #                'mspike_rasters=mspikes.mspike_rasters:main',
      #                'mspike_shape=mspikes.mspike_shape:main',
      #                'mspike_merge=mspikes.mspike_merge:main']},

      # install_requires=["numpy>=1.3", "scipy>=0.7", "arf>=1.1.0"],

      ext_package='mspikes',
      # ext_modules=[_readklu, _spikes]
)
