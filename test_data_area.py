# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""One data folder for everything SDS-Manager makes (v0.1.34)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import data_area


class DataAreaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.area = self.base / 'share' / 'sds100-database-favorites-manager'
        self.legacy = self.base / 'share' / 'SDS100DatabaseFavoritesManager'

    def make_legacy(self):
        versions = self.legacy / 'database' / 'versions' / 'HPDB-Experimental-10_25_2026'
        versions.mkdir(parents=True)
        (versions / 'hpdb.cfg').write_text('cfg')
        (self.legacy / 'database' / 'current').symlink_to(Path('versions') / versions.name)
        (self.legacy / 'database' / 'downloads').mkdir()
        (self.legacy / 'database' / 'downloads' / 'MasterHpdb_10_25_2026.gz').write_bytes(b'gz')
        (self.legacy / 'firmware').mkdir()
        (self.legacy / 'firmware' / 'SDS-100_V1_26_01.bin').write_bytes(b'fw')

    def test_old_folder_moves_in_and_becomes_a_link(self):
        self.make_legacy()
        self.area.mkdir(parents=True)
        (self.area / 'scanner-configurations').mkdir()
        report = data_area.migrate(self.area, self.legacy)
        self.assertTrue(report['linked'])
        self.assertEqual(report['kept'], [])
        self.assertTrue(self.legacy.is_symlink())
        self.assertEqual(self.legacy.resolve(), self.area.resolve())
        current = self.area / 'database' / 'current'
        self.assertTrue(current.is_symlink())                   # still points at its version
        self.assertEqual((current / 'hpdb.cfg').read_text(), 'cfg')
        self.assertTrue((self.legacy / 'database' / 'current' / 'hpdb.cfg').is_file())   # old path still works
        self.assertTrue((self.area / 'firmware' / 'SDS-100_V1_26_01.bin').is_file())
        self.assertTrue((self.area / 'scanner-configurations').is_dir())
        self.assertEqual(data_area.migrate(self.area, self.legacy), {'moved': 0, 'kept': [], 'linked': False})

    def test_nothing_overwritten_when_both_have_a_file(self):
        self.make_legacy()
        (self.area / 'firmware').mkdir(parents=True)
        (self.area / 'firmware' / 'SDS-100_V1_26_01.bin').write_bytes(b'newer')
        (self.area / 'firmware' / 'other.bin').write_bytes(b'x')
        report = data_area.migrate(self.area, self.legacy)
        self.assertFalse(report['linked'])
        self.assertEqual(len(report['kept']), 1)
        self.assertEqual((self.area / 'firmware' / 'SDS-100_V1_26_01.bin').read_bytes(), b'newer')
        self.assertEqual((self.legacy / 'firmware' / 'SDS-100_V1_26_01.bin').read_bytes(), b'fw')
        self.assertTrue((self.area / 'database' / 'current' / 'hpdb.cfg').is_file())    # the rest moved

    def test_no_old_folder(self):
        report = data_area.migrate(self.area, self.legacy)
        self.assertTrue(report['linked'])
        self.assertTrue(self.area.is_dir())

    def test_unique_and_names(self):
        folder = data_area.folder('exports', self.area)
        self.assertEqual(folder, self.area / 'exports')
        self.assertEqual(data_area.folder('downloads', self.area), self.area / 'database' / 'downloads')
        (folder / 'List.hpd').write_text('x')
        (folder / 'List (2).hpd').write_text('x')
        self.assertEqual(data_area.unique(folder, 'List.hpd').name, 'List (3).hpd')
        self.assertEqual(data_area.unique(folder, 'Other.hpd').name, 'Other.hpd')
        self.assertEqual(data_area.safe_name('Fire/EMS: "North"?'), 'Fire EMS North')
        self.assertEqual(data_area.safe_name('..'), 'SDS-Manager')
        self.assertEqual(data_area.stamp(__import__('datetime').datetime(2026, 11, 14, 13, 5, 9)), '2026-11-14 130509')

    def test_managed_storage_uses_the_area(self):
        import managed_storage
        self.assertEqual(managed_storage.ROOT, data_area.AREA)

    def test_chosen_archive_is_kept_in_downloads(self):
        import qt_stub
        with qt_stub.installed(forget=('database_favorites_manager',)):
            import database_favorites_manager as dfm
            source = self.base / 'Downloads' / 'MasterHpdb_10_25_2026.gz'
            source.parent.mkdir()
            source.write_bytes(b'archive')
            downloads = self.area / 'database' / 'downloads'
            kept = dfm.keep_archive_copy(source, downloads)
            self.assertEqual(kept, downloads / source.name)
            self.assertEqual(kept.read_bytes(), b'archive')
            self.assertTrue(source.is_file())                    # the original stays
            self.assertEqual(dfm.keep_archive_copy(source, downloads), kept)      # same file: used as it is
            self.assertEqual(dfm.keep_archive_copy(kept, downloads), kept.resolve())
            source.write_bytes(b'different')
            with self.assertRaises(ValueError):
                dfm.keep_archive_copy(source, downloads)
            self.assertEqual(list(downloads.glob('.*')), [])     # no partial files left

    def test_no_save_dialogs_left(self):
        """Files the program makes go into the data folder; it only asks when you bring a file in."""
        here = Path(__file__).resolve().parent
        for name in ('database_favorites_manager.py', 'keys_window.py', 'compare_dialog.py'):
            self.assertNotIn('getSaveFileName', (here / name).read_text(), name)
        main = (here / 'database_favorites_manager.py').read_text()
        self.assertEqual(main.count('getExistingDirectory'), 1)            # Import Existing Database only
        self.assertNotIn('SDS100-Research', main)

    def test_export_one_state_file_asks_nothing_for_the_output(self):
        import qt_stub
        with qt_stub.installed(forget=('database_favorites_manager',)):
            import database_favorites_manager as dfm
            window = mock.MagicMock()
            calls = {}

            def reconstruct(master, state, destination):
                calls['destination'] = Path(destination)
                return {'path': str(destination), 'records': 1, 'bytes': 1}
            with mock.patch.object(data_area, 'AREA', self.area), \
                    mock.patch.object(data_area, 'show_saved') as shown, \
                    mock.patch.object(dfm.QFileDialog, 'getOpenFileName', return_value=('/x/master.hp1', '')), \
                    mock.patch.object(dfm.QFileDialog, 'getSaveFileName') as save_dialog, \
                    mock.patch('PyQt6.QtWidgets.QInputDialog.getInt', return_value=(45, True)), \
                    mock.patch('hpdb_state_reconstruction.reconstruct_state', side_effect=reconstruct):
                dfm.ManagerWindow.reconstruct_one_state(window)
            save_dialog.assert_not_called()
            self.assertEqual(calls['destination'], self.area / 'database' / 'rebuilt' / 's_000045_rebuilt.hpd')
            self.assertEqual(shown.call_args[0][2], calls['destination'])

    def test_personal_download_goes_to_downloads(self):
        import edition
        if not edition.PERSONAL:
            self.skipTest('the Uniden download is in the personal build only')
        import qt_stub
        with qt_stub.installed(forget=('database_favorites_manager',)):
            import database_favorites_manager as dfm
            got = {}

            def download(name, user, password, folder):
                got['folder'] = Path(folder)
                return {'path': str(Path(folder) / name), 'bytes': 1, 'uncompressed_bytes': 1, 'records': 1}
            with mock.patch.object(data_area, 'AREA', self.area), \
                    mock.patch.object(data_area, 'show_saved'), \
                    mock.patch('uniden_hpdb_download.discover', return_value=['MasterHpdb_10_25_2026.gz']), \
                    mock.patch('uniden_hpdb_download.download', side_effect=download), \
                    mock.patch('PyQt6.QtWidgets.QInputDialog.getItem', return_value=('MasterHpdb_10_25_2026.gz', True)), \
                    mock.patch.object(dfm.QMessageBox, 'question', return_value=dfm.QMessageBox.StandardButton.Yes), \
                    mock.patch.object(dfm.QFileDialog, 'getExistingDirectory') as chooser:
                dfm.ManagerWindow.check_uniden_archives(mock.MagicMock())
            chooser.assert_not_called()
            self.assertEqual(got['folder'], self.area / 'database' / 'downloads')


if __name__ == '__main__':
    unittest.main()
