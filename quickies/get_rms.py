# -*- coding: utf-8 -*-
# -*- mode: python -*-
import sys
import numpy as nx
from mspikes.modules import neural_filter, util, arf_io
from collections import defaultdict

def get_stats(reader, *modules):

    out = defaultdict(list)
    def append(chunk):
        if "scalar" in chunk.tags:
            out[chunk.id].append((float(chunk.offset),) + chunk.data)

    with util.chain_modules(*(modules + (util.visitor(append),))) as chain:
        for chunk in reader:
            chain.send(chunk)

    return dict((k, nx.asarray(d)) for k, d in out.iteritems())

if __name__ == '__main__':

    _randg = nx.random.RandomState(1)
    # data = _randg.randn(1000000) * 1.2
    # stats = get_stats(util.array_reader(data, 10000, 5000), neural_filter.zscale(max_rms=2, window=60))

    scaler = neural_filter.zscale(exclude=True)
    reader = arf_io.arf_reader("examples/st445_1_5.arf", channels=("st445_(8|9)$",))
    reader.add_target(util.print_progress())
