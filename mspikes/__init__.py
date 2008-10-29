#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
modules for extracting and sorting spike data.

Component modules:

explog - reads explog files in native SABER format and a compressed
         hdf5-based format; parses native format to h5 format

klusters - contains code specific for reading and writing file formats
           used by klusters and klustakwik

extractor - functions for detecting and processing spike events
            (imported by klusters)

utils - general math and data processing functions

toelis - functions and class for manipulating time-of-event list data

"""

__version__ = "1.1.2"
__all__ = ['extractor','klusters','utils','explog','toelis']
