#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Module with some utility functions and classes for mspikes

Copyright (C) Dan Meliza, 2006-2009 (dmeliza@uchicago.edu)
Free for use under Creative Commons Attribution-Noncommercial-Share
Alike 3.0 United States License
(http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
"""
from collections import defaultdict

class defaultdict(defaultdict):
    """
    Improved defaultdict that passes key value to __missing__

    Example:
    >>> def lfactory(x): return [x]
    >>> dd = defaultdict(lfactory)
    >>> dd[1]
    [1]

    Makes a good handler of file objects.
    """
    def __missing__(self, key):
        if self.default_factory is None: raise KeyError((key,))
        self[key] = value = self.default_factory(key)
        return value


import numpy as nx
from scipy import weave
from scipy.linalg import get_blas_funcs, svd

def signalstats(S):
    """  Compute dc offset and rms from a signal  """

    assert S.ndim == 1, "signalstats() can only handle 1D arrays"
    out = nx.zeros((2,))
    code = """
         #line 618 "signalproc.py"
         double e = 0;
         double e2 = 0;
         double v;
         int nsamp = NS[0];
         for (int i = 0; i < nsamp; i++) {
              v = (double)S[i];
              e += v;
              e2 += v * v;
         }
         out[0] = e / nsamp;
         out[1] = sqrt(e2 / nsamp - out[0] * out[0]);

         """
    weave.inline(code, ['S','out'])
    return out


def fftresample(S, npoints, reflect=False, axis=0):
    """
    Resample a signal using discrete fourier transform. The signal
    is transformed in the fourier domain and then padded or truncated
    to the correct sampling frequency.  This should be equivalent to
    a sinc resampling.
    """
    from scipy.fftpack import rfft, irfft

    # this may be considerably faster if we do the memory operations in C
    # reflect at the boundaries
    if reflect:
        S = nx.concatenate([flipaxis(S,axis), S, flipaxis(S,axis)],
                           axis=axis)
        npoints *= 3

    newshape = list(S.shape)
    newshape[axis] = int(npoints)

    Sf = rfft(S, axis=axis)
    Sr = (1. * npoints / S.shape[axis]) * irfft(Sf, npoints, axis=axis, overwrite_x=1)
    if reflect:
        return nx.split(Sr,3)[1]
    else:
        return Sr

def flipaxis(data, axis):
    """
    Like fliplr and flipud but applies to any axis
    """

    assert axis < data.ndim
    slices = []
    for i in range(data.ndim):
        if i == axis:
            slices.append(slice(None,None,-1))
        else:
            slices.append(slice(None))
    return data[slices]


class filecache(dict):
    """
    Provides a cache of open file handles, indexed by name. If
    an attempt is made to access a file that's not open, the
    class tries to open the file
    """

    _handler = open

    def __gethandler(self):
        return self._handler
    def __sethandler(self, handler):
        self._handler = handler

    handler = property(__gethandler, __sethandler)

    def __getitem__(self, key):
        if self.__contains__(key):
            return dict.__getitem__(self, key)
        else:
            val = self._handler(key)
            dict.__setitem__(self, key, val)
            return val

    def __setitem__(self, key, value):
        raise NotImplementedError, "Use getter methods to add items to the cache"



def gemm(a,b,alpha=1.,**kwargs):
    """
    Wrapper for gemm in scipy.linalg.  Detects which precision to use,
    and alpha (result multiplier) is default 1.0.

    GEMM performs a matrix-matrix multiplation (or matrix-vector)

    C = alpha*op(A)*op(B) + beta*C

    A,B,C are matrices, alpha and beta are scalars
    op(X) is either X or X', depending on whether trans_a or trans_b are 1
    beta and C are optional

    op(A) must be m by k
    op(B) must be k by n
    C, if supplied, must be m by n

    set overwrite_c to 1 to use C's memory for output
    """
    _gemm,= get_blas_funcs(('gemm',),(a,b))
    return _gemm(alpha, a, b, **kwargs)


def pcasvd(data, output_dim=None):
    """
    Computes principal components of data using singular value decomposition.
    Data is centered prior to running svd.
    """
    if output_dim==None: output_dim = data.shape[1]
    data = data - data.mean(0)
    u,s,v = svd(data, full_matrices=0)
    v = v[:output_dim,:]
    return gemm(data, v, trans_b=1), v
