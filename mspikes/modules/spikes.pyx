# -*- coding: utf-8 -*-
# -*- mode: cython -*-
"""spike detection routines

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Wed Jul 24 09:26:36 2013
"""
cimport numpy as nx
nx.import_array()

cdef enum DetectorState:
    BELOW_THRESHOLD = 1
    BEFORE_PEAK = 2
    AFTER_PEAK = 3

cdef inline bint compare_sign(double x, double y):
    """return True iff ((x > 0) && (y > 0)) || ((x < 0) && (y < 0))"""
    return ((x > 0) and (y > 0)) or ((x < 0) and (y < 0))

cdef class detect_spikes:
    """Detect spikes in a continuous stream of samples.

    This implementation allows samples to be sent to the detector in blocks, and
    maintains state across successive calls.
    """

    cdef:

        double thresh
        double prev_val
        int n_after
        int n_after_crossing
        DetectorState state

    def __init__(self, thresh, n_after):
        """Construct spike detector.

        thresh -- the crossing threshold that triggers the detector. Positive
                  values imply positive-going crossings, and negative values
                  imply negative-going crossings

        n_after -- the maximum number of samples after threshold crossing to
                   look for the peak. If a peak has not been located within this
                   window, the crossing is considered an artifact and is not counted.

        """
        assert thresh != 0
        self.thresh = thresh
        self.n_after = n_after
        self.state = BELOW_THRESHOLD

    def send(self, nx.ndarray samples not None):
        """Detect spikes in a time series.

        Returns a list of indices corresponding to the peaks (or troughs) in the
        data. Retains state between calls. The detector should be reset if there
        is a gap in the signal.

        """
        cdef object x
        cdef int i = 0
        out = []

        cdef nx.flatiter it = <nx.flatiter> nx.PyArray_IterNew(samples)
        while nx.PyArray_ITER_NOTDONE(it):
            x = nx.PyArray_GETITEM(samples, nx.PyArray_ITER_DATA(it))
            if self.state is BELOW_THRESHOLD:
                if compare_sign(x - self.thresh, self.thresh):
                    self.prev_val = x
                    self.n_after_crossing = 0
                    self.state = BEFORE_PEAK
            elif self.state is BEFORE_PEAK:
                if compare_sign(self.prev_val - x, self.thresh):
                    out.append(i - 1)
                    self.state = AFTER_PEAK
                elif self.n_after_crossing > self.n_after:
                    self.state = BELOW_THRESHOLD
                else:
                    self.prev_val = x
                    self.n_after_crossing += 1
            elif self.state is AFTER_PEAK:
                if compare_sign(self.thresh - x, self.thresh):
                    self.state = BELOW_THRESHOLD
            nx.PyArray_ITER_NEXT(it)
            i += 1
        return out


# Variables:
# End:
