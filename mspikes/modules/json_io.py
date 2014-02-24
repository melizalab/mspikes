# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Read and write json-based event lists

Copyright (C) 2013 Dan Meliza <dan@meliza.org>
Created Fri Dec 20 14:41:47 2013
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import json

from mspikes import util
from mspikes.types import Node


class ArrayEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def get_stimulus_info(dset):
    """Returns dict of the first stimulus id, onset, and offset in dset.

    Currently we assume there's only one stimulus per trial. Raises an error if
    the dset doesn't have 'id' (or 'message'), 'start', and 'status' fields.

    """
    from operator import itemgetter

    out = {}
    ds = dset.attrs.get('sampling_rate', 1.0)
    # sort by start time to to ensure we get the first stimulus and that the
    # stop is after the start
    for r in sorted(dset, key=itemgetter('start')):
        try:
            id = r['id']
        except IndexError:
            id = r['message']
        status, time = r['status'], r['start']
        status &= 0xf0
        if 'stim' not in out:
            out['stim'] = id
        if out['stim'] == id:
            if status == 0x00:
                out['stim_on'] = time / ds
            elif status == 0x10:
                out['stim_off'] = time /ds
    return out


def write_datasets(trials, base_time, logger):
    """Writes trials to disk in evt-json format, splitting into separate files by key

    If the target file already exists (e.g., when data for a unit are split
    across multiple files), the trials are merged into the existing file. Trials
    already in the target file are skipped.

    """
    pass

class json_writer(Node):
    """Writes event data to json format.

    This module exports time of event (point process) data to evt-json format
    (see http://meliza.org/specs/evt-json), which allows data to be easily
    aligned and grouped using trial metadata. Each channel is written to a
    separate file.

    accepts: _events (marked or unmarked point process),
             _structure (trial info)
    emits: none

    """
    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("-c", "--channels",
                 help="""regular expression restricting which channels to write (default all event
        type channels). For example, 'pcm_000' will only match channels that
        start with 'pcm_000', including 'pcm_000' but also 'pcm_0001', etc. To
        match 'pcm_000' exactly, use 'pcm_000$'. You can also exclude specific
        channels using regular expressions. '(?!pcm_000)' will match any channel
        that doesn't start with 'pcm_000'. If multiple patterns are specified,
        channels that match any pattern will be included.""",
                 metavar='CH',
                 action='append')
        addopt_f("--stim-chan", help="""name of channel to use for stimulus
        markup (default '%(default)s'). This channel is not included in
        the list of output channels. Note: if this channel is filtered
        from the input side, the output json file won't have any
        stimulus information""", default="stimuli")
        addopt_f("--overwrite",
                 help="overwrite existing files (default is to merge by uuid)")

    def __init__(self, name, **options):
        import re
        Node.__init__(self, name)
        util.set_option_attributes(self, options, stim_chan="stimuli")

        try:
            self.chanp = util.any_regex(*options['channels'])
            self._log.info("only using channels that match '%s'", self.chanp.__doc__)
        except re.error, e:
            raise ValueError("bad channel regex: %s" % e.message)
        except (KeyError, TypeError):
            self.chanp = util.true_p

        self._trials = []
        # stores time of first entry
        self._base_offset = None
        # stores metadata for the entry extracted from structure chunks
        self._current_entry = None
        # stores data and metadata for current trial, indexed by channel
        self._current_trial = {}

    def send(self, chunk):
        from mspikes import register
        from arf import is_marked_pointproc, timestamp_to_float
        if "events" in chunk.tags:
            if chunk.id == self.stim_chan:
                self._current_trial['stim'] = get_stimulus_info(chunk.data)
            elif self.chanp(chunk.id):
                if is_marked_pointproc(chunk.data):
                    data = chunk.data['start']
                else:
                    data = chunk.data[:]
                try:
                    unit = register.get_by_id(chunk.id)['uuid']
                except KeyError:
                    unit = chunk.id
                self._current_trial[chunk.id] = {
                    'time': float(chunk.offset),
                    'unit': unit,
                    'trial_on': 0.0,
                    'events': data / (chunk.ds or 1.0)
                }

        elif "structure" in chunk.tags:
            # store current trial, updating with current stim info if it exists
            self._process_trial()
            self._current_entry = chunk
            if self._base_offset is None:
                self._base_offset = timestamp_to_float(chunk.data['timestamp'])

    def _process_trial(self):
        stimdata = self._current_trial.pop('stim', {})
        for t in self._current_trial.values():
            t['trial'] = self._current_entry.data['uuid']
            if 'trial_off' in self._current_entry.data:
                # more recent arfxplog-generated data, jrecord > 2.1.1
                t['trial_off'] = (self._current_entry.data['trial_off'] /
                                  self._current_entry.ds )
            elif "max_length" in self._current_entry.data:
                # older arfxplog files
                t['trial_off'] = self._current_entry.data['max_length']
            t.update(stimdata)
            try:
                self._log.debug("'%s': trial='%s', stim='%s', t=%f--%f",
                                self._current_entry.id, t['trial'], t['stim'],
                                t['stim_on'], t['stim_off'])
            except KeyError:
                self._log.debug("'%s' (trial '%s') has no stimulus",
                                self._current_entry.id, t['trial'])
            self._trials.append(t)
        self._current_trial.clear()

    def close(self):
        """Flushes data from the last trial"""
        self._process_trial()

    def __del__(self):
        """Writes json file on destruction"""
        import os.path
        from itertools import groupby
        from operator import itemgetter

        key = itemgetter('unit')
        for unitname, unit in groupby(sorted(self._trials, key=key), key=key):
            fname = unitname + '.json'
            if os.path.exists(fname):
                # merge with existing data
                data = json.load(open(fname, 'rU'))
                time_diff = self._base_offset - data['time']
                tgt_trials = data['trials']
                tgt_trial_count = len(tgt_trials)
                tgt_trial_ids = set(t['trial'] for t in tgt_trials)
                for trial in unit:
                    if trial['trial'] not in tgt_trial_ids:
                        trial['time'] += time_diff
                        tgt_trials.append(trial)
                    else:
                        self._log.debug("%s: trial '%s' already in file", unitname, trial['trial'])
                self._log.info("%s: merged trials into existing file (old: %d, new: %d)",
                            unitname, tgt_trial_count, len(tgt_trials))
            else:
                data = {'time': self._base_offset, 'trials': tuple(unit)}

            with open(fname, 'wt') as fp:
                json.dump(data, fp, indent=2, separators=(',', ': '), cls=ArrayEncoder)
            self._log.info("%s: wrote trial data", unitname)


# Variables:
# End:

