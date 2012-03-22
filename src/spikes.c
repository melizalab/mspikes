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
spike_times(short *out, const short *samples, int nsamples, int thresh, int window)
{
	int i,j, peak_ind;
	short peak_val;
	memset(out, 0, nsamples * sizeof(short));
	for (i = 0; i < nsamples; i++) {
		if (samples[i] > thresh) {
			peak_ind = i;
			peak_val = samples[i];
			for (j = i + 1; j < i + window; j++) {
				if (samples[j] > peak_val) {
					peak_val = samples[j];
					peak_ind = j;
				}
			}
			if (peak_ind > window && peak_ind + window < nsamples)
				out[peak_ind] = 1;
			/// search for first sample below threshold
			for (i = peak_ind; i < nsamples && samples[i] > thresh; ++i) {}
		}
	}
}

void
extract_spikes(double *out, const double *samples, int nsamples, const int *times, int ntimes,
	       int windowstart, int windowstop)
{
	const int window = windowstart + windowstop;
	int i, event;
	for (i = 0; i < ntimes; ++i) {
		event = times[i];
		if ((event - windowstart < 0) || (event + windowstop > nsamples)) continue;
		memcpy(out+(i*window), samples+event-windowstart, window*sizeof(double));
	}
}


void
signal_stats(double *out, const short *samples, int nsamples)
{
	 double e = 0;
	 double e2 = 0;
	 double v;
	 int i;
	 for (i = 0; i < nsamples; i++) {
	      v = (double)samples[i];
	      e += v;
	      e2 += v * v;
	 }
	 out[0] = e / nsamples;
	 out[1] = sqrt(e2 / nsamples - out[0] * out[0]);
}
