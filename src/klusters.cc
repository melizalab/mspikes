/*
 * klusters.cc
 *
 * A python extension module to read cluster and site files in
 * Klusters/KlustaKwik format
 *
 * Copyright (C) Dan Meliza, 2006-2012 (dmeliza@uchicago.edu)
 * Free for use under Creative Commons Attribution-Noncommercial-Share
 * Alike 3.0 United States License
 * (http://creativecommons.org/licenses/by-nc-sa/3.0/us/)
 *
 */
#include <Python.h>
#include <cstdio>
#include <vector>
#include <set>
#include <map>
using std::vector;
using std::set;
using std::map;

long
getclusters(FILE* cfp, set<int> &clusters)
{
	int clust, rp, fpos;
	long nlines = 0;
	fpos = ftell(cfp);
	fseek(cfp, 0, 0);
	rp = fscanf(cfp, "%d", &clust);  // throw away first line
	clusters.clear();
	while(rp != EOF) {
		rp = fscanf(cfp, "%d", &clust);
		clusters.insert(clust);
		nlines += 1;
	}
	fseek(cfp, fpos, 0);

	return nlines;
}

void
sort_unit(FILE* cfp, FILE* ffp, map<int, vector<long > > &uvec)
{
	int rp = 0;
	int nfeats;
	set<int> clusters;
	getclusters(cfp, clusters);

	// with one cluster, that's the one we use
	// with more than one cluster, we drop 0
	// if there's still more than one cluster, we drop 1
	if ((clusters.size()> 1) && (clusters.count(0)))
		clusters.erase(0);
	if ((clusters.size()> 1) && (clusters.count(1)))
		clusters.erase(1);

	uvec.clear();
	for (set<int>::const_iterator it = clusters.begin(); it != clusters.end(); it++) {
		int cluster = *it;
		uvec[cluster] = vector<long>(0);
	}

	int clust;
	long atime;
	rp = fscanf(ffp, "%d", &nfeats);
        rp = fscanf(cfp, "%d", &clust); // throw away first line
	while (rp != EOF) {
		for (int j = 0; j < nfeats && rp != EOF; j++)
			rp = fscanf(ffp, "%ld", &atime);
		rp = fscanf(cfp, "%d", &clust);
                if (rp == EOF) break;
		if (clusters.count(clust))
			uvec[clust].push_back(atime);
	}
}


/* Python interface */
static PyObject*
klusters_getclusters(PyObject* self, PyObject* args)
{
	const char *cname;
	if (!PyArg_ParseTuple(args, "s", &cname))
		return NULL;
	FILE *cfp;
	if ((cfp = fopen(cname, "rt"))==NULL) {
		PyErr_SetString(PyExc_IOError, "Unable to open file");
		return NULL;
	}

	set<int> clusters;
	getclusters(cfp, clusters);
	fclose(cfp);

	// construct a list of the clusters
	PyObject* out = PyList_New(clusters.size());
	int i = 0;
	for (set<int>::const_iterator it = clusters.begin(); it != clusters.end(); it++, i++)
		PyList_SetItem(out, i, PyInt_FromLong((long)*it));

	return out;
}

static PyObject*
klusters_sort_unit(PyObject* self, PyObject* args)
{
	const char *fname, *cname;
	vector<long> atimes;

	if (!PyArg_ParseTuple(args, "ss", &fname, &cname))
		return NULL;

	// open the files
	FILE *cfp, *ffp;
	if ((cfp = fopen(cname, "rt"))==NULL) {
		PyErr_Format(PyExc_IOError, "Unable to open file '%s'", cname);
		return NULL;
	}
	if ((ffp = fopen(fname, "rt"))==NULL) {
		PyErr_Format(PyExc_IOError, "Unable to open file '%s'", fname);
		return NULL;
	}


	// run the cluster grouping function
	map<int, vector<long> > uvec;
	sort_unit(cfp, ffp, uvec);

	fclose(cfp);
	fclose(ffp);

	// convert output to python lists
	PyObject *ulist, *events;
	ulist = PyList_New(0);

	for (map<int, vector<long> >::const_iterator it = uvec.begin(); it != uvec.end(); it++) {
		int unit = it->first;
		int nevents = uvec[unit].size();
		events = PyList_New(nevents);
		for (int j = 0; j < nevents; j++)
			PyList_SetItem(events, j, PyLong_FromLong(uvec[unit][j]));
		PyList_Append(ulist, events);   // does not decref rlist
		Py_DECREF(events);
	}

	return ulist;
}


static PyMethodDef klusters_methods[] = {
    {"getclusters",  klusters_getclusters, METH_VARARGS,
     "getclusters(clufile) -> a list of the clusters defined in the clu file."},
    {"sort_unit",  klusters_sort_unit, METH_VARARGS,
     "sort_unit(fetfile,clufile) -> lists of spike times, sorted by cluster."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

extern "C" {
PyMODINIT_FUNC
init_klusters(void)
{
    (void) Py_InitModule("_klusters", klusters_methods);
}
}
