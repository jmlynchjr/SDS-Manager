# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Update a Favorites List system from RadioReference (v0.1.35)."""
import copy
import tempfile
import unittest

import favorites_clipboard as fc
import rr_convert as rc
import rr_links
import rr_update as ru

DETAILS = {'sName': 'Palmetto 800', 'sType': 8, 'lat': 34.0, 'lon': -81.0, 'range': 150}
LAW, TAC, FIRE = ([{'tagDescr': 'Law Dispatch'}], [{'tagDescr': 'Law Tactical'}], [{'tagDescr': 'Fire Dispatch'}])


def sites(extra_freq=False, drop=False, nac='1DB', new_site=False):
    freqs = [{'lcn': 1, 'freq': 851.1875}, {'lcn': 2, 'freq': 851.875}]
    if drop:
        freqs = freqs[:1]
    if extra_freq:
        freqs.append({'lcn': 3, 'freq': 852.3375})
    out = [{'siteDescr': 'Greenville County Simulcast', 'nac': nac, 'lat': 34.88, 'lon': -82.34, 'range': 30,
            'siteFreqs': freqs}]
    if new_site:
        out.append({'siteDescr': 'Anderson', 'nac': '1DC', 'lat': 34.5, 'lon': -82.6, 'range': 20,
                    'siteFreqs': [{'lcn': 1, 'freq': 853.1}]})
    return out


CATS = [{'tgCid': 7, 'tgCname': 'Greenville City Police'}, {'tgCid': 8, 'tgCname': 'Greenville Fire'}]


def tgs(rename=False, service=False, new=False, gone=False, encrypt=False):
    rows = [{'tgDec': 44358, 'tgDescr': 'PD Dispatch' if rename else 'Police Dispatch', 'tgCid': 7,
             'tags': TAC if service else LAW},
            {'tgDec': 44359, 'tgDescr': 'Police Tac 1', 'tgCid': 7, 'tags': TAC, 'enc': 2 if encrypt else 0},
            {'tgDec': 44400, 'tgDescr': 'Fire Dispatch', 'tgCid': 8, 'tags': FIRE}]
    if gone:
        rows = [r for r in rows if r['tgDec'] != 44400]
    if new:
        rows.append({'tgDec': 44360, 'tgDescr': 'Police Tac 2', 'tgCid': 7, 'tags': TAC})
        rows.append({'tgDec': 44500, 'tgDescr': 'Animal Control', 'tgCid': 99, 'tags': []})
    return rows


def native(section):
    return fc.database_clip(section['records'])['records']


def trunk(**kw):
    section, why = rc.trunk_section(DETAILS, 'Project 25 Phase II', sites(**{k: v for k, v in kw.items() if k in
                                    ('extra_freq', 'drop', 'nac', 'new_site')}), CATS,
                                    tgs(**{k: v for k, v in kw.items() if k in ('rename', 'service', 'new', 'gone',
                                                                                 'encrypt')}))
    assert why is None, why
    return native(section)


def entries_for(records):
    meta = {'scope': 'metadata', 'key': ['native-copy-meta', 'f_000001.hpd'], 'records': [], 'encoding': 'cp1252',
            'source_path': '/x/f_000001.hpd'}
    return [meta, {'key': ['native-copy', '/x', 1], 'name': fc.system_name(records), 'kind': records[0][0],
                   'scope': 'system', 'records': copy.deepcopy(records), 'origin': 'native-copy'}]


def groups(changes):
    return [c['group'] for c in changes]


class TrunkTests(unittest.TestCase):
    def test_same_system_has_no_changes(self):
        self.assertEqual(ru.compare(trunk(), trunk()), [])

    def test_names_settings_new_and_gone_talkgroups(self):
        mine, theirs = trunk(), trunk(rename=True, service=True, new=True, gone=True)
        changes = ru.compare(mine, theirs)
        by = {c['group']: [x for x in changes if x['group'] == c['group']] for c in changes}
        self.assertEqual(len(by['tg_names']), 1)
        self.assertFalse(by['tg_names'][0]['default'])            # a name someone may have chosen: not ticked
        self.assertIn('Police Dispatch → PD Dispatch', by['tg_names'][0]['text'])
        self.assertTrue(by['tg_settings'][0]['default'])
        new = {c['text']: c['default'] for c in by['tg_new']}
        self.assertTrue(any('Police Tac 2' in t and d for t, d in new.items()))           # department I have
        self.assertTrue(any('Animal Control' in t and 'new department' in t and not d for t, d in new.items()))
        self.assertFalse(by['tg_gone'][0]['default'])

    def test_apply_keeps_my_settings(self):
        mine, theirs = trunk(), trunk(rename=True, service=True, new=True)
        entries = entries_for(mine)
        records = entries[1]['records']
        dispatch = next(r for r in records if r[0] == 'TGID' and r[5] == '44358')
        dispatch[14] = '12'                                  # my number tag
        dispatch[4] = 'On'                                   # my avoid
        changes = ru.compare(records, theirs)
        report = ru.apply(entries, 1, changes)              # tick everything
        dispatch = next(r for r in records if r[0] == 'TGID' and r[5] == '44358')
        self.assertEqual((dispatch[3], dispatch[7], dispatch[14], dispatch[4]), ('PD Dispatch', '7', '12', 'On'))
        tgids = [r[5] for r in records if r[0] == 'TGID']
        self.assertIn('44360', tgids)
        self.assertIn('44500', tgids)
        self.assertEqual(len(tgids), len(set(tgids)))
        self.assertIn('Other talkgroups', [r[3] for r in records if r[0] == 'T-Group'])
        self.assertGreaterEqual(report['added'], 2)
        self.assertEqual(ru.compare(records, theirs), [])

    def test_unticked_changes_are_left_alone(self):
        mine, theirs = trunk(), trunk(rename=True, new=True)
        entries = entries_for(mine)
        changes = ru.compare(entries[1]['records'], theirs)
        ru.apply(entries, 1, [c for c in changes if c['default']])
        names = {r[5]: r[3] for r in entries[1]['records'] if r[0] == 'TGID'}
        self.assertEqual(names['44358'], 'Police Dispatch')
        self.assertNotIn('44500', names)
        self.assertIn('44360', names)

    def test_site_frequencies_nac_and_new_site(self):
        mine, theirs = trunk(), trunk(extra_freq=True, drop=True, nac='1DD', new_site=True)
        changes = ru.compare(mine, theirs)
        self.assertEqual(sorted(set(groups(changes))), ['freq_gone', 'freq_new', 'site_new', 'site_settings'])
        entries = entries_for(mine)
        ru.apply(entries, 1, changes)
        records = entries[1]['records']
        freqs = [r[5] for r in records if r[0] == 'T-Freq']
        self.assertIn('852337500', freqs)
        self.assertNotIn('851875000', freqs)
        self.assertIn('Anderson', [r[3] for r in records if r[0] == 'Site'])
        self.assertEqual(next(r for r in records if r[0] == 'Site')[17], '1DD')
        anderson = [b for b in fc.blocks(records) if b[0] == 'Site' and records[b[1]][3] == 'Anderson'][0]
        self.assertTrue(any(records[i][0] == 'BandPlan_P25' for i in range(anderson[1], anderson[2])))
        self.assertLess(anderson[1], next(b[1] for b in fc.blocks(records) if b[0] == 'T-Group'))
        self.assertEqual(ru.compare(records, theirs), [])

    def test_renamed_site_matches_by_frequencies(self):
        mine = trunk()
        next(r for r in mine if r[0] == 'Site')[3] = 'GVL Simulcast'
        self.assertEqual(ru.compare(mine, trunk()), [])

    def test_never_the_last_talkgroup_of_a_department(self):
        mine = trunk()
        theirs = trunk(gone=True)                            # Fire Dispatch, alone in Greenville Fire, is gone
        entries = entries_for(mine)
        changes = ru.compare(entries[1]['records'], theirs)
        report = ru.apply(entries, 1, changes)
        self.assertIn('44400', [r[5] for r in entries[1]['records'] if r[0] == 'TGID'])
        self.assertIn('last', report['kept'][0][1])

    def test_never_the_last_site_frequency(self):
        mine = trunk()
        section, _ = rc.trunk_section(DETAILS, 'Project 25 Phase II',
                                      [{'siteDescr': 'Greenville County Simulcast', 'nac': '1DB',
                                        'siteFreqs': [{'lcn': 1, 'freq': 860.0}]}], CATS, tgs())
        theirs = native(section)
        entries = entries_for(mine)
        changes = ru.compare(entries[1]['records'], theirs)
        ru.apply(entries, 1, [c for c in changes if c['group'] == 'freq_gone'])   # removals only
        self.assertEqual(len([r for r in entries[1]['records'] if r[0] == 'T-Freq']), 1)
        entries = entries_for(mine)
        ru.apply(entries, 1, ru.compare(entries[1]['records'], theirs))           # with the new one: all go
        self.assertEqual([r[5] for r in entries[1]['records'] if r[0] == 'T-Freq'], ['860000000'])

    def test_encrypted_now_counts_as_gone(self):
        changes = ru.compare(trunk(), trunk(encrypt=True))
        self.assertEqual(groups(changes), ['tg_gone'])
        self.assertIn('44359', changes[0]['text'])

    def test_different_types_refused(self):
        mine = trunk()
        theirs = copy.deepcopy(mine)
        theirs[0][6] = 'DmrOneFrequency'
        with self.assertRaises(ru.UpdateError):
            ru.compare(mine, theirs)
        with self.assertRaises(ru.UpdateError):
            ru.compare(mine, conventional())

    def test_changed_rows_are_checked_before_use(self):
        mine, theirs = trunk(), trunk(rename=True)
        entries = entries_for(mine)
        changes = ru.compare(entries[1]['records'], theirs)
        del entries[1]['records'][2]                         # the list changed since: positions moved
        ru.apply(entries, 1, changes)
        self.assertNotIn('PD Dispatch', [r[3] for r in entries[1]['records']])


SUB = {'scid': 11, 'scName': 'Fire', 'lat': 34.85, 'lon': -82.39, 'range': 25}
LAWSUB = {'scid': 12, 'scName': 'Law', 'lat': 34.85, 'lon': -82.39, 'range': 25}


def conventional(tone='107.2 PL', name='Fire Dispatch', new=False, gone=False, mode='FM'):
    fire = [{'out': 154.43, 'descr': name, 'mode': mode, 'tone': tone, 'tags': FIRE},
            {'out': 154.28, 'descr': 'Fireground', 'mode': 'FMN', 'tone': '023 DPL', 'tags': []}]
    if gone:
        fire = fire[:1]
    groups_ = [(SUB, fire)]
    if new:
        fire.append({'out': 154.19, 'descr': 'Fire Tac 3', 'mode': 'FMN', 'tone': '', 'tags': []})
        groups_.append((LAWSUB, [{'out': 155.55, 'descr': 'Sheriff', 'mode': 'FM', 'tone': '', 'tags': LAW}]))
    return native({'records': rc.conventional_section('Greenville County', groups_)['records']})


class ConventionalTests(unittest.TestCase):
    def test_same_is_no_change(self):
        self.assertEqual(ru.compare(conventional(), conventional()), [])

    def test_tone_name_mode_new_and_gone(self):
        changes = ru.compare(conventional(), conventional(tone='110.9 PL', name='Fire Disp', new=True, mode='NFM'))
        self.assertEqual(sorted(set(groups(changes))), ['ch_names', 'ch_new', 'ch_settings'])
        settings = next(c for c in changes if c['group'] == 'ch_settings')
        self.assertIn('tone CTCSS 107.2 → CTCSS 110.9', settings['text'])
        self.assertEqual(ru.audio_text('NAC=293'), 'NAC 293')
        self.assertEqual(ru.audio_text(''), 'none')
        new = {c['text']: c['default'] for c in changes if c['group'] == 'ch_new'}
        self.assertTrue(any('Fire Tac 3' in t and d for t, d in new.items()))
        self.assertTrue(any('Sheriff' in t and not d for t, d in new.items()))
        gone = ru.compare(conventional(), conventional(gone=True))
        self.assertEqual(groups(gone), ['ch_gone'])

    def test_apply_conventional(self):
        mine = conventional()
        theirs = conventional(tone='110.9 PL', new=True)
        entries = entries_for(mine)
        records = entries[1]['records']
        ch = next(r for r in records if r[0] == 'C-Freq' and r[5] == '154430000')
        ch[16] = '5'                                         # my number tag
        ru.apply(entries, 1, ru.compare(records, theirs))
        ch = next(r for r in records if r[0] == 'C-Freq' and r[5] == '154430000')
        self.assertEqual((ch[7], ch[16]), ('TONE=C110.9', '5'))
        self.assertIn('Law', [r[3] for r in records if r[0] == 'C-Group'])
        self.assertEqual(ru.compare(records, theirs), [])

    def test_placeholder_names_are_ticked(self):
        mine = conventional(name='154.4300')
        changes = ru.compare(mine, conventional())
        self.assertTrue(next(c for c in changes if c['group'] == 'ch_names')['default'])
        self.assertTrue(ru.placeholder('TGID 1234', '1234'))
        self.assertTrue(ru.placeholder('', '1'))
        self.assertFalse(ru.placeholder('My Fire', '154430000'))


class LinkTests(unittest.TestCase):
    def test_remember_get_and_forget(self):
        with tempfile.TemporaryDirectory() as area:
            records = trunk()
            self.assertIsNone(rr_links.get('Home', 'f_000001.hpd', records, area))
            rr_links.remember('Home', 'f_000001.hpd', records, ('trs', 6060), 'Palmetto 800', 45, None, area)
            link = rr_links.get('Home', 'f_000001.hpd', records, area)
            self.assertEqual((link['key'], link['label'], link['state']), (('trs', 6060), 'Palmetto 800', 45))
            renamed = copy.deepcopy(records)
            renamed[0][3] = 'Something else'
            self.assertIsNone(rr_links.get('Home', 'f_000001.hpd', renamed, area))
            rr_links.forget('Home', 'f_000001.hpd', records, area)
            self.assertIsNone(rr_links.get('Home', 'f_000001.hpd', records, area))

    def test_source_and_bad_files(self):
        self.assertEqual(rr_links.parse_source('rr:trs:6060'), ('trs', 6060))
        self.assertIsNone(rr_links.parse_source('/home/x/s_000045.hpd'))
        with tempfile.TemporaryDirectory() as area:
            rr_links.path(area).write_text('not json')
            self.assertEqual(rr_links.load(area), {})


if __name__ == '__main__':
    unittest.main()
