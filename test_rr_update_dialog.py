# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Update from RadioReference (v0.1.35): the window and the links, driven on the Qt stub with a fake account."""
import copy
import importlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import favorites_clipboard as fc
import qt_stub
import rr_links
import rr_source
from test_rr_convert import FakeClient
from test_rr_update import entries_for

FORGET = ('rr_update_dialog', 'database_workspace', 'state_labels', 'favorites_explorer', 'favorites_planner')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_area = rr_links.data_area.AREA
        rr_links.data_area.AREA = Path(self.tmp.name)            # never the real data folder
        self.addCleanup(setattr, rr_links.data_area, 'AREA', self.old_area)
        with qt_stub.installed(forget=FORGET):
            self.rud = importlib.import_module('rr_update_dialog')
            self.dw = importlib.import_module('database_workspace')
        for cls in (self.rud.RRUpdateDialog, self.rud.ChooseRRSystemDialog):
            cls._get_child_mock = lambda _self, **kw: MagicMock(**kw)
        self.browser = rr_source.RRBrowser(FakeClient())
        section, why = self.browser.load(('trs', 6060))
        records = fc.database_clip(section['records'])['records']
        self.records_now = records
        mine = copy.deepcopy(records)
        tg = next(r for r in mine if r[0] == 'TGID')
        tg[3] = 'TGID ' + tg[5]                               # an unnamed talkgroup: RadioReference's name is suggested
        tg[14] = '7'                                         # my number tag
        mine.append(['T-Group', '', '', 'My own', 'Off', '0.000000', '0.000000', '0.0', 'Circle', 'Off'])
        mine.append(['TGID', '', '', 'Old channel', 'Off', '99999', 'ALL', '21', '2', '0', 'Off', 'Auto', 'Off',
                     'On', 'Off', 'Off', 'Any'])
        self.entries = entries_for(mine)
        ws = SimpleNamespace(drafts={'List': self.entries}, current_draft='List', _snapshot=MagicMock(),
                             refresh_draft=MagicMock(), _rr_client_browser=lambda: self.browser,
                             region_choice=MagicMock(), county_choice=MagicMock())
        ws._rr_run = lambda what, work, done: done(work(self.browser), None)
        self.window = SimpleNamespace(workspace=ws, active_scanner_configuration='/configs/Home',
                                      save_draft_to_configuration=MagicMock(),
                                      _refresh_configuration_label=MagicMock(),
                                      _config_folder=lambda title: Path('/configs/Home'))
        self.ws = ws


class DialogTests(Fixture):
    def test_check_and_apply(self):
        records = self.entries[1]['records']
        rr_links.remember('Home', 'f_000001.hpd', records, ('trs', 6060), 'Palmetto 800', 45, None)
        d = self.rud.RRUpdateDialog(self.window, 'List')
        d.chosen_entries = lambda: [('List', 1)]
        d.check_changes()
        changes, label = d.results[('List', 1)]
        self.assertEqual(label, 'Palmetto 800')
        texts = {c['group']: c for c in changes}
        self.assertTrue(texts['tg_names']['default'])
        self.assertFalse(texts['tg_gone']['default'])
        d.ticked = lambda: {('List', 1): [c for c in changes if c['default']]}
        self.rud.QMessageBox.question = MagicMock(return_value=self.rud.YES)
        d.apply_changes()
        self.assertTrue(d.applied)
        self.ws._snapshot.assert_called_once()
        self.window.save_draft_to_configuration.assert_called_once()
        tg = next(r for r in records if r[0] == 'TGID' and r[14] == '7')
        self.assertFalse(tg[3].startswith('TGID '))
        self.assertIn('99999', [r[5] for r in records if r[0] == 'TGID'])      # unticked: kept

    def test_unlinked_system_asks_to_choose(self):
        d = self.rud.RRUpdateDialog(self.window, 'List')
        d.chosen_entries = lambda: [('List', 1)]
        d.check_changes()
        self.assertEqual(d.results, {})

    def test_mixin_needs_a_native_list_and_account(self):
        win = self.window
        win.update_list_from_rr = self.rud.RRUpdateMixin.update_list_from_rr.__get__(win)
        win._update_ready = self.rud.RRUpdateMixin._update_ready.__get__(win)
        self.ws.drafts['Plain'] = [{'scope': 'system'}]
        self.ws.current_draft = 'Plain'
        self.rud.QMessageBox.information = MagicMock()
        self.assertFalse(win.update_list_from_rr())
        self.assertIn('Favorites List', self.rud.QMessageBox.information.call_args[0][2])

    def test_choose_dialog_lists_matching_systems(self):
        chooser = self.rud.ChooseRRSystemDialog(self.ws, self.entries[1]['records'])
        self.assertEqual(chooser.kind, 'Trunk')
        self.assertEqual(self.rud.plain_name('Greenville County (conventional)'), 'greenville county')


class CheckAllListsTests(Fixture):
    def test_every_list_in_one_window(self):
        records = self.entries[1]['records']
        second = entries_for(copy.deepcopy(records))
        second[0]['source_path'] = '/x/f_000002.hpd'
        third = entries_for(copy.deepcopy(records))
        third[0]['source_path'] = '/x/f_000003.hpd'                 # not linked: shown, not ticked
        rr_links.remember('Home', 'f_000001.hpd', records, ('trs', 6060), 'Palmetto 800', 45, None)
        rr_links.remember('Home', 'f_000002.hpd', second[1]['records'], ('trs', 6060), 'Palmetto 800', 45, None)
        lists = {'List': self.entries, 'Second': second, 'Third': third}
        loads = []
        real_load = self.browser.load
        self.browser.load = lambda key: loads.append(key) or real_load(key)
        d = self.rud.RRUpdateDialog(self.window, None, None, None, 'rr', lists)
        self.assertTrue(d.all_lists)
        self.assertEqual(d.system_entries(), [('List', 1), ('Second', 1), ('Third', 1)])
        self.assertIsNone(d.link_for(('Third', 1)))
        d.chosen_entries = lambda: [('List', 1), ('Second', 1)]
        d.check_changes()
        self.assertEqual(len(loads), 1)                             # the same system is read once
        self.assertEqual(set(d.results), {('List', 1), ('Second', 1)})
        d.ticked = lambda: {key: [c for c in changes if c['default']] for key, (changes, _l) in d.results.items()}
        self.rud.QMessageBox.question = MagicMock(return_value=self.rud.YES)
        d.apply_changes()
        self.ws._snapshot.assert_called_once()                       # one Undo step for every list
        for entries in (self.entries, second):
            tg = next(r for r in entries[1]['records'] if r[0] == 'TGID' and r[14] == '7')
            self.assertFalse(tg[3].startswith('TGID '))
        tg = next(r for r in third[1]['records'] if r[0] == 'TGID' and r[14] == '7')
        self.assertTrue(tg[3].startswith('TGID '))

    def test_menu_needs_lists(self):
        win = self.window
        win.check_all_lists = self.rud.RRUpdateMixin.check_all_lists.__get__(win)
        win._update_ready = self.rud.RRUpdateMixin._update_ready.__get__(win)
        win._list_drafts = lambda: {}
        self.rud.QMessageBox.information = MagicMock()
        self.assertFalse(win.check_all_lists())
        self.assertIn('no Favorites Lists', self.rud.QMessageBox.information.call_args[0][2])


class LinkOnAddTests(Fixture):
    def test_added_from_radioreference_remembers_the_system(self):
        section, _ = self.browser.load(('trs', 6060))
        fake = SimpleNamespace(drafts={'List': self.entries},
                               window=lambda: SimpleNamespace(active_scanner_configuration='/configs/Home'),
                               region_choice=MagicMock(currentData=MagicMock(return_value=('rr-state', 45))),
                               county_choice=MagicMock(currentData=MagicMock(return_value=2335)))
        self.dw.DatabaseWorkspace._remember_rr_link(fake, 'List', section, 'rr:trs:6060')
        link = rr_links.get('Home', 'f_000001.hpd', self.records_now)
        self.assertEqual((link['key'], link['state'], link['county']), (('trs', 6060), 45, 2335))

    def test_uniden_database_source_is_not_linked(self):
        section, _ = self.browser.load(('trs', 6060))
        fake = SimpleNamespace(drafts={'List': self.entries})
        self.dw.DatabaseWorkspace._remember_rr_link(fake, 'List', section, '/db/s_000045.hpd')
        self.assertEqual(rr_links.load(), {})


if __name__ == '__main__':
    unittest.main()
