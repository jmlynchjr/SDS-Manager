# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Compare the open configuration with the scanner (v0.1.32)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config_compare as cc

FIX = Path(__file__).resolve().parent / 'test_fixtures'


def _edit(path, old, new, count=1):
    raw = path.read_bytes()
    assert old in raw, old
    path.write_bytes(raw.replace(old, new, count))


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.scanner = base / 'card' / 'BCDx36HP'
        self.config = base / 'configs' / 'test'
        self.local = self.config / 'BCDx36HP'
        for root in (self.scanner, self.local):
            (root / 'favorites_lists').mkdir(parents=True)
            (root / 'profile.cfg').write_bytes((FIX / 'real_sds100_profile.cfg').read_bytes())
            for name in ('f_000001.hpd', 'f_000002.hpd'):
                (root / 'favorites_lists' / name).write_bytes((FIX / ('real_sds100_' + name)).read_bytes())
            (root / 'favorites_lists' / 'f_list.cfg').write_bytes((FIX / 'real_sds100_f_list.cfg').read_bytes())
        # no remembered export state in tests
        patcher = mock.patch('export_state.matched_avoids', lambda c, path=None: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_compare(self):
        return cc.compare(self.config, self.scanner.parent)

    def test_identical(self):
        result = self.run_compare()
        self.assertTrue(result['identical'])
        self.assertEqual(cc.summary(result)[0], 'The scanner matches this configuration.')
        self.assertTrue(all(l['status'] == 'same' for l in result['lists']))
        self.assertIn('Nothing was written', '\n'.join(cc.report_lines(result)))

    def test_channel_field_change(self):
        lines = (self.local / 'favorites_lists' / 'f_000001.hpd').read_bytes().split(b'\r\n')
        index = next(i for i, l in enumerate(lines) if l.startswith(b'C-Freq\t'))
        row = lines[index].split(b'\t')
        row[10] = b'5' if row[10] != b'5' else b'2'          # Delay
        lines[index] = b'\t'.join(row)
        (self.local / 'favorites_lists' / 'f_000001.hpd').write_bytes(b'\r\n'.join(lines))
        result = self.run_compare()
        self.assertFalse(result['identical'])
        item = next(l for l in result['lists'] if l['filename'] == 'f_000001.hpd')
        self.assertEqual(item['status'], 'different')
        self.assertEqual(len(item['changed']), 1)
        self.assertEqual(item['changed'][0]['kind'], 'C-Freq')
        self.assertEqual([f[0] for f in item['changed'][0]['fields']], ['Delay'])
        self.assertFalse(item['added'] or item['removed'])

    def test_added_and_removed_talkgroup(self):
        path = self.local / 'favorites_lists' / 'f_000001.hpd'
        lines = path.read_bytes().split(b'\r\n')
        index = next(i for i, l in enumerate(lines) if l.startswith(b'TGID\t'))
        row = lines[index].split(b'\t')
        row[5] = b'65000'
        row[3] = b'New TG'
        del lines[index]
        lines.insert(index, b'\t'.join(row))
        path.write_bytes(b'\r\n'.join(lines))
        item = next(l for l in self.run_compare()['lists'] if l['filename'] == 'f_000001.hpd')
        self.assertEqual([a['kind'] for a in item['added']], ['TGID'])
        self.assertIn('New TG (TGID 65000)', item['added'][0]['label'])
        self.assertEqual([r['kind'] for r in item['removed']], ['TGID'])
        report = '\n'.join(cc.report_lines(self.run_compare()))
        self.assertIn('+ Talkgroup', report)
        self.assertIn('− Talkgroup', report)

    def test_avoid_shown_in_words(self):
        path = self.scanner / 'favorites_lists' / 'f_000001.hpd'
        lines = path.read_bytes().split(b'\r\n')
        index = next(i for i, l in enumerate(lines) if l.startswith(b'C-Freq\t'))
        row = lines[index].split(b'\t')
        row[4] = b'On'
        lines[index] = b'\t'.join(row)
        path.write_bytes(b'\r\n'.join(lines))
        item = next(l for l in self.run_compare()['lists'] if l['filename'] == 'f_000001.hpd')
        self.assertEqual(item['changed'][0]['fields'][0][:2], ('Avoid', 'Permanent Avoid'))

    def test_avoid_made_on_scanner_is_marked(self):
        path = self.scanner / 'favorites_lists' / 'f_000001.hpd'
        import scanner_avoids
        before = scanner_avoids.configuration_avoids(self.config)
        lines = path.read_bytes().split(b'\r\n')
        index = next(i for i, l in enumerate(lines) if l.startswith(b'C-Freq\t'))
        row = lines[index].split(b'\t')
        row[4] = b'On'
        lines[index] = b'\t'.join(row)
        path.write_bytes(b'\r\n'.join(lines))
        with mock.patch('export_state.matched_avoids', lambda c, path=None: before):
            item = next(l for l in self.run_compare()['lists'] if l['filename'] == 'f_000001.hpd')
        self.assertIn('changed on the scanner', item['changed'][0]['fields'][0][2])

    def test_list_only_on_one_side(self):
        (self.scanner / 'favorites_lists' / 'f_000002.hpd').unlink()
        (self.local / 'favorites_lists' / 'f_000009.hpd').write_bytes(
            (FIX / 'real_sds100_f_000001.hpd').read_bytes())
        statuses = {l['filename']: l['status'] for l in self.run_compare()['lists']}
        self.assertEqual(statuses['f_000002.hpd'], 'configuration only')
        self.assertEqual(statuses['f_000009.hpd'], 'configuration only')
        (self.local / 'favorites_lists' / 'f_000001.hpd').unlink()
        statuses = {l['filename']: l['status'] for l in self.run_compare()['lists']}
        self.assertEqual(statuses['f_000001.hpd'], 'scanner only')

    def test_list_setting_difference(self):
        from flist_settings import read_lists, edits_between, patch_lists
        cfg = self.local / 'favorites_lists' / 'f_list.cfg'
        old = read_lists(cfg.read_bytes())
        new = [dict(l) for l in old]
        new[0]['monitor'] = 'Off' if old[0]['monitor'] == 'On' else 'On'
        cfg.write_bytes(patch_lists(cfg.read_bytes(), edits_between(old, new)))
        result = self.run_compare()
        item = next(l for l in result['lists'] if l['filename'] == old[0]['filename'].lower())
        self.assertEqual(item['status'], 'different')
        self.assertTrue(any('Monitor' in s for s in item['settings']))

    def test_profile_setting_difference(self):
        import profile_schema
        raw = (self.local / 'profile.cfg').read_bytes()
        kind = next(k for k, spec in profile_schema.SCHEMA.items() if spec['rows'] == 1
                    and profile_schema.read_section(raw, k)
                    and any(f.kind == 'choice' and len(f.values) > 1 and v in f.values for f, v in
                            zip(profile_schema.fields_of(k, profile_schema.read_section(raw, k)[0]),
                                profile_schema.read_section(raw, k)[0])))
        row = profile_schema.read_section(raw, kind)[0]
        fields = profile_schema.fields_of(kind, row)
        position = next(i for i, f in enumerate(fields, 1)
                        if f.kind == 'choice' and len(f.values) > 1 and row[i - 1] in f.values)
        choices = fields[position - 1].values
        value = next(c for c in choices if c != row[position - 1])
        (self.local / 'profile.cfg').write_bytes(profile_schema.patch_fields(raw, {(kind, 0, position): value}))
        result = self.run_compare()
        self.assertEqual(len(result['profile']), 1)
        self.assertFalse(result['identical'])

    def test_line_endings_only(self):
        path = self.local / 'favorites_lists' / 'f_000001.hpd'
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        item = next(l for l in self.run_compare()['lists'] if l['filename'] == 'f_000001.hpd')
        self.assertEqual(item['status'], 'same')
        self.assertIn('Same content', item['note'])

    def test_nothing_written(self):
        def snapshot():
            return {p: hashlib.sha256(p.read_bytes()).hexdigest()
                    for root in (self.scanner, self.local) for p in root.rglob('*') if p.is_file()}
        before = snapshot()
        cc.report_lines(self.run_compare())
        self.assertEqual(before, snapshot())

    def test_not_a_scanner(self):
        with self.assertRaises(ValueError):
            cc.compare(self.config, Path(self.tmp.name))


class WindowTest(CompareTest):
    """The window and menu action run end to end against the Qt stand-in."""

    def test_dialog_and_action(self):
        import qt_stub
        from unittest.mock import MagicMock
        path = self.local / 'favorites_lists' / 'f_000001.hpd'
        lines = path.read_bytes().split(b'\r\n')
        del lines[next(i for i, l in enumerate(lines) if l.startswith(b'TGID\t'))]
        path.write_bytes(b'\r\n'.join(lines))
        with qt_stub.installed(forget=('compare_dialog',)):
            import compare_dialog as cd
            # a Qt subclass built on the stand-in makes its child mocks plain ones
            cd.CompareDialog._get_child_mock = lambda self, **kw: MagicMock(**kw)
            result = self.run_compare()
            dialog = cd.CompareDialog(MagicMock(), result, 'test')
            dialog.hide_same.isChecked = lambda: False
            dialog.fill()
            self.assertIn('(only on the scanner)', dialog.report())
            config, scanner = self.config, str(self.scanner.parent)
            shown = []

            class Window(cd.CompareMixin):
                active_scanner_configuration = config
                _db_update_busy = False

                def _modified_list_names(self):
                    return []

                def pick_scanner_folder(self, title):
                    return scanner

                def _scanner_operation_running(self, what=''):
                    return False

                def _run_background(self, title, text, work, done):
                    done(work(), None)

            with __import__('unittest').mock.patch.object(cd, 'CompareDialog',
                                                         lambda *a: shown.append(a) or MagicMock()):
                Window().compare_configuration_with_scanner()
            self.assertEqual(len(shown), 1)
            self.assertFalse(shown[0][1]['identical'])


if __name__ == '__main__':
    unittest.main()
