# -*- coding: utf-8 -*-
# -*- mode: python -*-
import sys
if sys.hexversion < 0x02060000:
    raise RuntimeError("Python 2.6 or higher required")

from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages, Extension
import numpy

try:
    from Cython.Distutils import build_ext
    SUFFIX = '.pyx'
except ImportError:
    from distutils.command.build_ext import build_ext
    SUFFIX = '.c'

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

compiler_settings = {
    'include_dirs' : [numpy.get_include()],
    }

_spikes = Extension('mspikes.modules.spikes', sources=['mspikes/modules/spikes' + SUFFIX],
                    **compiler_settings)

requirements = ["arf==2.1"]
if sys.hexversion < 0x02070000:
    requirements.append("argparse==1.2.1")

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
      url = "https://github.com/dmeliza/mspikes",

      packages=find_packages(),
      ext_modules=[_spikes],
      cmdclass = {'build_ext': build_ext},
      entry_points={'console_scripts':
                    ['mspikes=mspikes.main:mspikes']},
      test_suite = 'nose.collector',
      install_requires = requirements
)
