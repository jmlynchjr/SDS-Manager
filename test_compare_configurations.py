# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Compare two saved configurations, or one with a scanner backup (v0.1.38)."""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import config_compare as cc

FIX = Path(__file__).resolve().parent / 'test_fixtures'


def make_folder(root):
    (root / 'BCDx36HP' / 'favorites_lists').mkdir(parents=True)
    (root / 'BCDx36HP' / 'profile.cfg').write_bytes((FIX / 'real_sds100_profile.cfg').read_bytes())
    for name in ('f_000001.hpd', 'f_000002.hpd'):
        (root / 'BCDx36HP' / 'favorites_lists' / name).write_bytes((FIX / ('real_sds100_' + name)).read_bytes())
    (root / 'BCDx36HP' / 'favorites_lists' / 'f_list.cfg').write_bytes((FIX / 'real_sds100_f_list.cfg').read_bytes())
    return root


class TwoConfigurationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.first = make_folder(base / 'configs' / 'home')
        self.second = make_folder(base / 'configs' / 'travel')
        self.backup = make_folder(base / 'scanner-backups' / '20261114T204812Z')
        self.sides = cc.configuration_sides('Home', 'Travel')
        patcher = mock.patch('export_state.matched_avoids', lambda c, path=None: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_same(self):
        result = cc.compare(self.first, self.second, self.sides)
        self.assertTrue(result['identical'])
        self.assertEqual(cc.summary(result)[0], 'Home and Travel are the same.')
        report = '\n'.join(cc.report_lines(result, 'Home'))
        self.assertIn('COMPARE TWO CONFIGURATIONS', report)
        self.assertIn('Nothing was written to Travel or Home.', report)
        self.assertNotIn('scanner', report.lower().replace('scanner settings', ''))

    def test_differences_use_the_names(self):
        (self.second / 'BCDx36HP' / 'favorites_lists' / 'f_000002.hpd').unlink()
        path = self.first / 'BCDx36HP' / 'favorites_lists' / 'f_000001.hpd'
        lines = path.read_bytes().split(b'\r\n')
        del lines[next(i for i, l in enumerate(lines) if l.startswith(b'TGID\t'))]
        path.write_bytes(b'\r\n'.join(lines))
        result = cc.compare(self.first, self.second, self.sides)
        headline, short = cc.summary(result)
        self.assertEqual(headline, 'Home and Travel differ.')
        self.assertIn('1 Favorites List only in Home', short)
        report = '\n'.join(cc.report_lines(result, 'Home'))
        self.assertIn('(only in Travel)', report)
        self.assertIn('ONLY IN HOME', report)
        self.assertEqual(cc.status_text('scanner only', self.sides), 'Only in Travel')

    def test_with_a_scanner_backup(self):
        sides = cc.configuration_sides('Home', 'Scanner backup 2026-11-14 20:48 UTC')
        result = cc.compare(self.first, self.backup, sides)
        self.assertTrue(result['identical'])

    def test_no_avoid_notes_between_configurations(self):
        with mock.patch.object(cc, '_avoid_notes', side_effect=AssertionError('not for two configurations')):
            cc.compare(self.first, self.second, self.sides)

    def test_scanner_wording_unchanged(self):
        result = cc.compare(self.first, self.second)
        self.assertEqual(cc.summary(result)[0], 'The scanner matches this configuration.')
        self.assertEqual(cc.status_text('configuration only'), 'Only in the configuration')

    def test_nothing_written(self):
        def snapshot():
            return {p: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in Path(self.tmp.name).rglob('*') if p.is_file()}
        before = snapshot()
        cc.report_lines(cc.compare(self.first, self.second, self.sides))
        self.assertEqual(before, snapshot())


class ChoicesAndWindowTest(TwoConfigurationsTest):
    def load(self):
        import importlib
        import qt_stub
        with qt_stub.installed(forget=('compare_dialog',)):
            cd = importlib.import_module('compare_dialog')
        for cls in (cd.CompareDialog, cd.ChooseComparisonDialog):
            cls._get_child_mock = lambda _self, **kw: MagicMock(**kw)
        return cd

    def test_choices_order(self):
        cd = self.load()
        configurations = [(self.second, {'name': 'Travel'}), (self.first, {'name': 'Home'})]
        backups = [{'name': '20261101T100000Z', 'path': Path('/b/1')},
                   {'name': '20261114T204812Z', 'path': self.backup}]
        choices = cd.comparison_choices(configurations, backups, self.second)
        labels = [label for label, _f in choices]
        self.assertEqual(labels, ['Travel (open)', 'Home', 'Scanner backup 2026-11-14 20:48 UTC',
                                  'Scanner backup 2026-11-01 10:00 UTC'])
        self.assertEqual(cd.short_name('Travel (open)'), 'Travel')
        self.assertEqual(cd.backup_label('20261114T204812Z-2'), '2026-11-14 20:48 UTC #2')

    def test_window_and_action(self):
        cd = self.load()
        (self.second / 'BCDx36HP' / 'favorites_lists' / 'f_000002.hpd').unlink()
        result = cc.compare(self.first, self.second, self.sides)
        dialog = cd.CompareDialog(MagicMock(), result, 'Home')
        self.assertFalse(dialog.scanner_mode)
        dialog.hide_same.isChecked = lambda: False
        dialog.fill()
        self.assertIn('Only in Home: 1 trunked system', dialog.report())
        first, second = self.first, self.second
        shown = []

        class Window(cd.CompareMixin):
            active_scanner_configuration = first

            def _modified_list_names(self):
                return []

            def _run_background(self, title, text, work, done):
                done(work(), None)

        cd.ChooseComparisonDialog.exec = lambda _self: cd.QDialog.DialogCode.Accepted
        cd.ChooseComparisonDialog.chosen = lambda _self: (('Home', str(first)), ('Travel', str(second)))
        cd.CompareDialog.exec = lambda _self: shown.append(_self.comparison)
        with mock.patch('scanner_configurations.list_configurations',
                        lambda: [(first, {'name': 'Home'}), (second, {'name': 'Travel'})]), \
                mock.patch('scanner_backup.list_backups', lambda: []):
            Window().compare_two_configurations()
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]['sides']['Old'], 'Travel')

    def test_nothing_to_compare(self):
        cd = self.load()
        cd.QMessageBox.information = MagicMock()

        class Window(cd.CompareMixin):
            active_scanner_configuration = None
        with mock.patch('scanner_configurations.list_configurations', lambda: [(self.first, {'name': 'Home'})]), \
                mock.patch('scanner_backup.list_backups', lambda: []):
            Window().compare_two_configurations()
        self.assertIn('nothing to compare', cd.QMessageBox.information.call_args[0][2])


if __name__ == '__main__':
    unittest.main()
