# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Check Heard Talkgroups with RadioReference (v0.1.39): Monitor history → unknown talkgroups → RadioReference →
added and named, on a list built from the fake RadioReference system (Palmetto 800, sid 6060), and the window on
the Qt stub. Nothing is read from or written to the real Monitor or data folders."""
import copy
import csv
import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import favorites_clipboard as fc
import heard_check as hc
import monitor_link
import qt_stub
import rr_links
import rr_source
import scanner_list_sync as sync
from test_rr_convert import FakeClient
from test_rr_update import entries_for

TODAY = date(2026, 11, 17)


def write_history(folder, day, rows):
    path = Path(folder) / 'history' / f'reception_history_{day}.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(monitor_link.MONITOR_HISTORY_HEADERS)
        w.writerows(rows)


def call(day, time, system, channel, tgid, seconds=3):
    return [f'{day} {time}', f'{day} {time}', str(seconds), system, 'Dept', channel, '859.262500MHz',
            f'TGID:{tgid}', '-60']


def raw(rows):
    return ('\r\n'.join('\t'.join(r) for r in rows) + '\r\n').encode('cp1252')


def rows_of(entries):
    """The list as a native file: the header the scanner needs, then every system."""
    return [['TargetModel', 'BCDx36HP'], ['FormatVersion', '1.00']] + \
        [r for e in entries if e.get('scope') != 'metadata' for r in e['records']]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.browser = rr_source.RRBrowser(FakeClient())
        section, _why = self.browser.load(('trs', 6060))
        records = fc.database_clip(section['records'])['records']
        mine = [r for r in records if not (r[0] == 'TGID' and r[5] in ('44357', '44356', '50001'))]
        unnamed = next(r for r in mine if r[0] == 'TGID' and r[5] == '44358')
        unnamed[3] = 'TGID 44358'
        self.records = mine
        self.drafts = {'Home': entries_for(mine)}
        folder = self.tmp.name
        write_history(folder, '2026-11-15', [
            call('2026-11-15', '10:00:00', 'Palmetto 800', 'TGID 44358', '44358'),      # unnamed in the list
            call('2026-11-15', '10:01:00', 'Palmetto 800', '44357', '44357'),           # missing (fully encrypted)
            call('2026-11-15', '10:02:00', 'Palmetto 800', 'Traffic Ops', '44356'),     # missing, the scanner showed a name
            call('2026-11-15', '10:03:00', 'Palmetto 800', '50001', '50001'),           # missing, no category
            call('2026-11-15', '10:04:00', 'Palmetto 800', '12345', '12345'),           # not on RadioReference
            call('2026-11-15', '10:05:00', 'Elsewhere 700', 'Ops', '777'),              # system not in the lists
        ])
        write_history(folder, '2026-11-16', [call('2026-11-16', '11:00:00', 'Palmetto 800', 'Traffic Ops', '44356')])
        write_history(folder, '2026-09-01', [call('2026-09-01', '09:00:00', 'Palmetto 800', 'Old', '99999')])
        self.heard = hc.heard_talkgroups(30, folder, TODAY)


class LogicTests(Fixture):
    def test_heard_in_the_window(self):
        self.assertIn(('palmetto 800', '44356'), self.heard)
        self.assertNotIn(('palmetto 800', '99999'), self.heard)                 # older than 30 days
        tg = self.heard[('palmetto 800', '44356')]
        self.assertEqual((tg['calls'], tg['shown'], tg['last'][:10]), (2, 'Traffic Ops', '2026-11-16'))
        self.assertEqual(self.heard[('palmetto 800', '44357')]['shown'], '')     # only the ID: no name

    def test_unknown_talkgroups(self):
        items = {i['tgid']: i for i in hc.unknown_talkgroups(self.heard, self.drafts)}
        self.assertEqual(items['44358']['status'], 'unnamed')
        self.assertEqual(items['44357']['status'], 'missing')
        self.assertEqual(items['777']['status'], 'no_system')
        self.assertEqual(len(items['44358']['locations']), 1)
        self.assertEqual(items['44356']['systems'], [('Home', 1)])
        named = [r for r in self.records if r[0] == 'TGID' and r[3] and not monitor_link.is_placeholder_name(r[3], r[5])]
        for row in named:                                                       # named talkgroups aren't listed
            self.assertNotIn(row[5], items)
        self.assertEqual(list(items)[-1], '777')                               # can't-add ones last

    def test_radioreference_info(self):
        info = hc.fetch_rr(self.browser, 6060)
        self.assertEqual(info['44358']['name'], 'Police Dispatch')
        self.assertEqual(info['44358']['category'], 'Greenville City Police')
        self.assertEqual(info['44358']['service'], '2')                          # Law Dispatch
        self.assertTrue(info['44357']['encrypted'])
        self.assertTrue(info['44356']['partly_encrypted'])
        self.assertEqual(info['44356']['name'], 'GVL PD Traffic')                # no description: the alpha tag
        self.assertEqual(info['50001']['category'], '')
        self.assertNotIn('12345', info)
        calls = len(self.browser.client.calls)
        hc.fetch_rr(self.browser, 6060)
        self.assertEqual(len(self.browser.client.calls), calls)                  # kept for the session

    def test_suggestions(self):
        info = hc.fetch_rr(self.browser, 6060)
        items = {i['tgid']: i for i in hc.unknown_talkgroups(self.heard, self.drafts)}
        self.assertEqual(hc.suggested(items['44358'], info['44358']), ('Police Dispatch', 'Greenville City Police', True))
        self.assertFalse(hc.suggested(items['44357'], info['44357'])[2])        # fully encrypted: not ticked
        self.assertEqual(hc.suggested(items['50001'], info['50001'])[1], hc.FALLBACK_DEPARTMENT)
        self.assertEqual(hc.suggested(items['12345'], None), ('', hc.FALLBACK_DEPARTMENT, False))
        self.assertEqual(hc.suggested(items['44356'], None)[0], 'Traffic Ops')   # the scanner's name without RR

    def test_apply(self):
        info = hc.fetch_rr(self.browser, 6060)
        items = {i['tgid']: i for i in hc.unknown_talkgroups(self.heard, self.drafts)}
        choices = []
        for tgid in ('44358', '44356', '50001'):
            name, department, _tick = hc.suggested(items[tgid], info[tgid])
            choices.append((items[tgid], name, department, info[tgid]['service']))
        named, added, made = hc.apply(self.drafts, choices)
        self.assertEqual((named, added, made), (1, 2, 1))
        records = self.drafts['Home'][1]['records']
        by_id = {r[5]: r for r in records if r[0] == 'TGID'}
        self.assertEqual(by_id['44358'][3], 'Police Dispatch')
        self.assertEqual((by_id['44356'][3], by_id['44356'][7]), ('GVL PD Traffic', '7'))
        self.assertEqual(hc.departments(records)[-1], hc.FALLBACK_DEPARTMENT)
        # 44356 went into the existing Greenville City Police department, before the next department starts.
        index = records.index(by_id['44356'])
        group = max(i for i in range(index) if records[i][0] == 'T-Group')
        self.assertEqual(records[group][3], 'Greenville City Police')
        ok, why = sync.assess_new_hpd(raw(rows_of(self.drafts['Home'])))
        self.assertTrue(ok, why)
        with self.assertRaises(ValueError):
            hc.apply(self.drafts, [(items['44356'], 'Again', 'X', '21')])          # already there now

    def test_list_changed_is_refused(self):
        items = {i['tgid']: i for i in hc.unknown_talkgroups(self.heard, self.drafts)}
        before = copy.deepcopy(self.drafts)
        self.drafts['Home'][1]['records'].insert(2, ['T-Group', '', '', 'Moved', 'Off', '0', '0', '0', 'Circle', 'Off'])
        with self.assertRaises(ValueError):
            hc.apply(self.drafts, [(items['44358'], 'Police Dispatch', '', '2')])
        self.assertNotEqual(self.drafts, before)                                   # (the caller undoes)


class WindowTests(Fixture):
    def setUp(self):
        super().setUp()
        self.old_area = rr_links.data_area.AREA
        rr_links.data_area.AREA = Path(self.tmp.name) / 'area'
        self.addCleanup(setattr, rr_links.data_area, 'AREA', self.old_area)
        with qt_stub.installed(forget=('heard_check_dialog', 'rr_update_dialog')):
            self.hcd = importlib.import_module('heard_check_dialog')
        self.hcd.HeardCheckDialog._get_child_mock = lambda _self, **kw: MagicMock(**kw)
        ws = SimpleNamespace(drafts=self.drafts, _snapshot=MagicMock(), undo_change=MagicMock(),
                             refresh_draft=MagicMock(), status=MagicMock())
        ws._rr_run = lambda what, work, done: done(work(self.browser), None)
        self.window = SimpleNamespace(workspace=ws, active_scanner_configuration='/configs/Home')
        self.ws = ws

    def dialog(self):
        return self.hcd.HeardCheckDialog(self.window, self.drafts, heard=self.heard)

    def test_needs_a_link(self):
        d = self.dialog()
        self.assertEqual([label for _k, label, _w in d.system_keys()], ['Palmetto 800', 'Elsewhere 700'])
        calls = len(self.browser.client.calls)
        d.look_up()
        self.assertEqual(d.rr, {})
        self.assertEqual(len(self.browser.client.calls), calls)                   # nothing asked without a link

    def test_look_up_and_apply(self):
        rr_links.remember('Home', 'f_000001.hpd', self.drafts['Home'][1]['records'], ('trs', 6060), 'Palmetto 800')
        d = self.dialog()
        d.look_up()
        rows = {r['item']['tgid']: r for r in d.rows}
        self.assertTrue(rows['44358']['tick'])
        self.assertFalse(rows['44357']['tick'])                                   # fully encrypted
        self.assertFalse(rows['12345']['tick'])                                   # not on RadioReference
        self.assertFalse(rows['777']['tick'])                                     # can't be added
        self.assertEqual(rows['44356']['department'], 'Greenville City Police')
        rows['12345'].update(tick=True, name='Water Rescue', department='Rescue')
        self.assertTrue(d.apply_ticked(confirm=False))
        self.ws._snapshot.assert_called_once()
        by_id = {r[5]: r for r in self.drafts['Home'][1]['records'] if r[0] == 'TGID'}
        self.assertEqual(by_id['44358'][3], 'Police Dispatch')
        self.assertEqual(by_id['12345'][3], 'Water Rescue')
        self.assertIn('Rescue', hc.departments(self.drafts['Home'][1]['records']))
        self.assertNotIn('44357', by_id)
        self.assertTrue(d.applied)
        left = {r['item']['tgid'] for r in d.rows}
        self.assertEqual(left, {'44357', '777'})                                  # the rest is done

    def test_bad_name_is_refused(self):
        rr_links.remember('Home', 'f_000001.hpd', self.drafts['Home'][1]['records'], ('trs', 6060), 'Palmetto 800')
        d = self.dialog()
        d.look_up()
        rows = {r['item']['tgid']: r for r in d.rows}
        rows['12345'].update(tick=True, name='   ')
        self.assertFalse(d.apply_ticked(confirm=False))
        self.ws._snapshot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
