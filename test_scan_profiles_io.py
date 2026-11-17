# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Import and export scan profiles (v0.1.33), on real SDS100 files."""
import json
import shutil
import unittest
from unittest import mock

import keys_model as km
import scan_profiles_io as spio
from test_list_sync_export import SyncBase


def swap_first_two(local):
    """The same lists, but Greenville County and SC Highway Patrol swap file numbers."""
    lists = local / 'favorites_lists'
    cfg = lists / 'f_list.cfg'
    raw = cfg.read_bytes().replace(b'f_000001.hpd', b'@@').replace(b'f_000002.hpd', b'f_000001.hpd')
    cfg.write_bytes(raw.replace(b'@@', b'f_000002.hpd'))
    (lists / 'f_000001.hpd').rename(lists / 'tmp.hpd')
    (lists / 'f_000002.hpd').rename(lists / 'f_000001.hpd')
    (lists / 'tmp.hpd').rename(lists / 'f_000002.hpd')


class MatchTests(unittest.TestCase):
    def test_by_name_then_file_name(self):
        source = {'f_000001.hpd': 'Greenville', 'f_000002.hpd': 'Highway', 'f_000003.hpd': 'Gone',
                  'f_000004.hpd': 'Renamed'}
        target = {'f_000002.hpd': 'Greenville', 'F_000001.hpd': 'Highway', 'f_000004.hpd': 'New name'}
        self.assertEqual(spio.match_lists(source, target),
                         {'f_000001.hpd': 'f_000002.hpd', 'f_000002.hpd': 'F_000001.hpd',
                          'f_000004.hpd': 'f_000004.hpd'})

    def test_a_name_used_twice_is_not_trusted(self):
        source = {'f_000001.hpd': 'Same', 'f_000002.hpd': 'Same'}
        target = {'f_000009.hpd': 'Same', 'f_000002.hpd': 'Other'}
        self.assertEqual(spio.match_lists(source, target), {'f_000002.hpd': 'f_000002.hpd'})

    def test_file_name_not_taken_twice(self):
        source = {'f_000001.hpd': 'A', 'f_000002.hpd': 'B'}
        target = {'f_000002.hpd': 'A'}
        self.assertEqual(spio.match_lists(source, target), {'f_000001.hpd': 'f_000002.hpd'})

    def test_bad_profiles_refused(self):
        for bad in ({}, {'fl': [True] * 99}, {'fl': [True] * 100, 'sys': {'f_000001.hpd': [1]}},
                    {'fl': [True] * 100, 'monitor': []}, 'text'):
            with self.assertRaises(ValueError):
                spio.clean_profile(bad)

    def test_unique_names(self):
        self.assertEqual(spio.unique_name('Home', {'Home': 1, 'Home (2)': 1}), 'Home (3)')
        self.assertEqual(spio.unique_name('Storm', {'Home': 1}), 'Storm')


class ImportTests(SyncBase):
    def setUp(self):
        super().setUp()
        self.other = self.configs / 'other'
        shutil.copytree(self.local, self.other / 'BCDx36HP')
        swap_first_two(self.other / 'BCDx36HP')

    def storm(self):
        m = km.model_for_configuration(self.config)
        greenville = next(i for i in m.items if i['level'] == 'list' and i['name'] == 'Greenville County')
        police = next(i for i in m.items if i['level'] == 'department' and i['name'] == 'Greenville (City) - Police')
        m.set_monitor(greenville, False)
        m.set_on(police, False)
        return m.profile()

    def test_from_another_configuration_follows_list_names(self):
        km.save_profiles(self.config, {'Storm': self.storm()})
        incoming, names = spio.from_configuration(self.config)
        merged, report = spio.merge({}, incoming, names, spio.list_names(self.other))
        self.assertEqual(report[0]['left_out'], [])
        km.save_profiles(self.other, merged)
        target = km.model_for_configuration(self.other)
        self.assertEqual(target.apply_profile(km.load_profiles(self.other)['Storm']), [])
        greenville = next(i for i in target.items if i['level'] == 'list' and i['name'] == 'Greenville County')
        highway = next(i for i in target.items if i['level'] == 'list' and i['name'] == 'SC Highway Patrol')
        police = next(i for i in target.items if i['level'] == 'department'
                      and i['name'] == 'Greenville (City) - Police')
        self.assertEqual(greenville['ref'][1], 'f_000002.hpd')        # moved, and still found
        self.assertFalse(greenville['monitor'])
        self.assertTrue(highway['monitor'])
        self.assertFalse(target.key_on(police))

    def test_list_missing_in_target_is_reported(self):
        km.save_profiles(self.config, {'Storm': self.storm()})
        incoming, names = spio.from_configuration(self.config)
        target = spio.list_names(self.other)
        del target['f_000002.hpd']                                     # Greenville isn't here
        _merged, report = spio.merge({}, incoming, names, target)
        self.assertEqual(report[0]['left_out'], ['Greenville County'])

    def test_names_kept_or_replaced(self):
        km.save_profiles(self.config, {'Home': self.storm()})
        incoming, names = spio.from_configuration(self.config)
        existing = {'Home': km.model_for_configuration(self.other).profile()}
        merged, report = spio.merge(existing, incoming, names, spio.list_names(self.other))
        self.assertEqual(sorted(merged), ['Home', 'Home (2)'])
        self.assertEqual(report[0]['saved_as'], 'Home (2)')
        merged, _ = spio.merge(existing, incoming, names, spio.list_names(self.other), replace=True)
        self.assertEqual(sorted(merged), ['Home'])
        self.assertNotEqual(merged['Home'], existing['Home'])

    def test_file_round_trip(self):
        km.save_profiles(self.config, {'Storm': self.storm()})
        path = self.base / 'profiles.json'
        spio.write_file(path, km.load_profiles(self.config), spio.list_names(self.config), 'test')
        self.assertEqual(json.loads(path.read_text())['format'], spio.FORMAT)
        incoming, names = spio.read_file(path)
        self.assertEqual(names['f_000001.hpd'], 'Greenville County')
        merged, report = spio.merge({}, incoming, names, spio.list_names(self.other))
        self.assertEqual(merged['Storm']['monitor']['f_000002.hpd'], False)   # Greenville, renumbered

    def test_bare_profiles_file_matches_by_file_name(self):
        km.save_profiles(self.config, {'Storm': self.storm()})
        incoming, names = spio.read_file(km.profiles_path(self.config))
        self.assertEqual(names, {})
        merged, _ = spio.merge({}, incoming, names, spio.list_names(self.config))
        self.assertEqual(merged['Storm'], spio.clean_profile(self.storm()))

    def test_bad_files(self):
        for content in ('not json', '[]', '{}', json.dumps({'format': spio.FORMAT, 'profiles': {'x': {}}})):
            path = self.base / 'bad.json'
            path.write_text(content)
            with self.assertRaises(ValueError):
                spio.read_file(path)

    def test_from_scanner(self):
        incoming, names = spio.from_scanner(self.scanner.parent, 'Scanner now')
        self.assertEqual(list(incoming), ['Scanner now'])
        self.assertEqual(incoming['Scanner now'], spio.clean_profile(km.model_for_configuration(self.config).profile()))
        self.assertEqual(spio.from_scanner(self.scanner, 'x')[0]['x'], incoming['Scanner now'])
        self.assertEqual(names['f_000001.hpd'], 'Greenville County')

    def test_window_import_and_export(self):
        """The Keys & Tags buttons run end to end against the Qt stand-in."""
        import qt_stub
        km.save_profiles(self.other, {'Home': km.model_for_configuration(self.other).profile(),
                                      'Storm': self.storm()})
        with qt_stub.installed(forget=('keys_window',)):
            import keys_window as kw
            K = kw.KeysWindow

            class Window:                    # the window's own methods on a plain object
                _fill_profiles, _title = K._fill_profiles, K._title
                _import_profiles, _export_profiles = K._import_profiles, K._export_profiles

            window = Window()
            window.folder, window.main = self.config, mock.MagicMock()
            window.model = km.model_for_configuration(self.config)
            window.profile_choice, window.summary = mock.MagicMock(), mock.MagicMock()
            window._fill_profiles()
            sources = ['Another saved configuration']
            with mock.patch.object(kw.QInputDialog, 'getItem', side_effect=[
                        (sources[0], True), (None, True)]) as get_item, \
                    mock.patch.object(Window, '_choose_profiles', create=True, new=lambda *a: (['Storm'], False)), \
                    mock.patch('scanner_configurations.list_configurations',
                               return_value=[(self.config, {'name': 'Test'}), (self.other, {'name': 'Other'})]):
                get_item.side_effect = lambda *a, **k: (a[3][0], True)
                window._import_profiles()
            self.assertEqual(sorted(km.load_profiles(self.config)), ['Storm'])
            window.main.pick_scanner_folder.return_value = str(self.scanner.parent)
            with mock.patch.object(kw.QInputDialog, 'getItem', side_effect=lambda *a, **k: (a[3][2], True)), \
                    mock.patch.object(kw.QInputDialog, 'getText', return_value=('Scanner now', True)):
                window._import_profiles()
            self.assertEqual(sorted(km.load_profiles(self.config)), ['Scanner now', 'Storm'])
            import data_area
            with mock.patch.object(data_area, 'AREA', self.base / 'area'), \
                    mock.patch.object(data_area, 'show_saved') as shown, \
                    mock.patch.object(Window, '_choose_profiles', create=True, new=lambda *a: (['Storm'], False)):
                window._export_profiles()
            path = shown.call_args[0][2]
            self.assertEqual(path, str(self.base / 'area' / 'exports' / 'test scan profiles.json'))
            self.assertEqual(list(spio.read_file(path)[0]), ['Storm'])


if __name__ == '__main__':
    unittest.main()
