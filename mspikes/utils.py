#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""
Module with some utility functions and classes for mspikes
"""

import numpy as nx
from scipy import weave
from scipy.linalg import get_blas_funcs, svd
import functools

def signalstats(S):
    """  Compute dc offset and rms from a signal  """
    # we want to compute these stats simultaneously
    # it's 200x faster than .mean() and .var()!

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



_manycolors = ['b','g','r','#00eeee','m','y',
               'teal',  'maroon', 'olive', 'orange', 'steelblue', 'darkviolet',
               'burlywood','darkgreen','sienna','crimson',
               ]
    
def colorcycle(ind=None, colors=_manycolors):
    """
    Returns the color cycle, or a color cycle, for manually advancing
    line colors.
    """
    if ind != None:
        return colors[ind % len(colors)]
    else:
        return colors


def drawoffscreen(f):
    from pylab import isinteractive, ion, ioff, draw
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        retio = isinteractive()
        ioff()
        try:
            y = f(*args, **kwargs)
        finally:
            if retio: ion()
            draw()
        return y
    return wrapper

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


def cov(m, y=None, rowvar=1, bias=0):
    """
    Like scipy.cov, but uses lapack for the matrix product
    """
    X = nx.array(m, ndmin=2, dtype=float)
    if X.shape[0] == 1:
        rowvar = 1
    if rowvar:
        axis = 0
        tup = (slice(None),nx.newaxis)
    else:
        axis = 1
        tup = (nx.newaxis, slice(None))


    if y is not None:
        y = nx.array(y, copy=False, ndmin=2, dtype=float)
        X = nx.concatenate((X,y),axis)

    X -= X.mean(axis=1-axis)[tup]
    if rowvar:
        N = X.shape[1]
    else:
        N = X.shape[0]

    if bias:
        fact = N*1.0
    else:
        fact = N-1.0

    if rowvar:
        return gemm(X, X.conj(), alpha=1/fact, trans_b=1).squeeze()
    else:
        return gemm(X, X.conj(), alpha=1/fact, trans_a=1).squeeze()
