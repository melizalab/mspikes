/* @(#)spikes.c
 *
 * Various C functions for analyzing extracellular data.
 *
 * Copyright (C) Dan Meliza, 2006-2012 (dmeliza@uchicago.edu)
 * Free for use under Creative Commons Attribution-Noncommercial-Share
 * Alike 3.0 United States License
 * (http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
 */

#include <string.h>
#include <math.h>

void
moments(double *out, const double *samples, int nsamples)
{
        memset(out, 0, 2 * sizeof(double));
        double v;
        int i;
        for (i = 0; i < nsamples; i++) {
	      v = samples[i];
	      out[0] += v;
	      out[1] += v * v;
	 }
}
