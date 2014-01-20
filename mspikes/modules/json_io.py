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
from mspikes.types import Node, MspikesError


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
    out = {}
    ds = dset.attrs.get('sampling_rate', 1.0)
    for r in dset:
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


class json_writer(Node):
    """Writes event data to json format.

    This module is used to export time of event (point process) data to json-evt
    format (see http://meliza.org/specs/json-evt), which allows data to be
    easily aligned and grouped using trial metadata.

    accepts: _events (marked or unmarked point process),
             _structure (trial info)
    emits: none

    """
    @classmethod
    def options(cls, addopt_f, **defaults):
        addopt_f("file",
                 help="path of output file (warning: overwrites existing file)",)
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
        addopt_f("--stim-chan",
                 help="name of channel to use for stimulus markup (default '%(default)s')."
                 " This channel is not included in the list of output channels.",
                 default="stimuli")
        addopt_f("--unit-file",
                 help="If set, writes attributes for each unit to a file named after "
                 "the unit uuid")

    def __init__(self, name, file, **options):
        import re
        Node.__init__(self, name)
        util.set_option_attributes(self, options, stim_chan="stimuli")
        self._fname = file
        self._log.info("output file: '%s'", self._fname)

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
                    unit = register.get_properties(chunk.id)['uuid']
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
                self._log.debug("'%s' (trial '%s') stimulus is '%s'",
                                self._current_entry.id, t['trial'], t['stim'])
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
        with open(self._fname, 'wt') as fp:
            json.dump({'time': self._base_offset, 'trials': self._trials},
                      fp, indent=2, separators=(',', ': '), cls=ArrayEncoder)
        self._log.info("wrote trial data to '%s'", self._fname)


# Variables:
# End:

















