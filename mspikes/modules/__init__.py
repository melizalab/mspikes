# -*- coding: utf-8 -*-
# -*- mode: python -*-

from stream_sink import stream_sink
from random_sources import rand_samples
from arf_io import arf_reader, arf_writer
from neural_filter import zscale
from util import splitter, print_progress
from spike_extraction import spike_extract, spike_features
from klusters import klusters_writer, klusters_reader
from plotting import collect_stats
#from file_io import file_reader, file_writer


def _module_list():
    import inspect
    return inspect.getmembers(inspect.getmodule(_module_list),
                              lambda x: callable(x) and not x.__name__.startswith('_'))
