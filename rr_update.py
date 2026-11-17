# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Update a system in a Favorites List from RadioReference (v0.1.35).

compare() sets a system of a Favorites List (the scanner's own rows) beside the same system as RadioReference
has it now (also as the scanner's own rows: rr_convert, then favorites_clipboard.database_clip, exactly as
Add to Favorites writes them) and lists what differs, as changes the user ticks or unticks:

    trunked:      talkgroup names; talkgroup service type and DMR timeslot; new talkgroups; talkgroups no
                  longer on RadioReference (or now fully encrypted); site frequencies added and removed;
                  site NAC, channel numbers (LCN) and colour codes; new sites; sites not on RadioReference
    conventional: channel names; modulation, tone / NAC / colour code and service type; new channels;
                  channels no longer on RadioReference

apply() makes the ticked changes. Nothing else in the list is touched: quick keys, number tags, avoids,
alerts, delays, locations and names you didn't tick keep their values. New items come in with RadioReference's
values and the scanner's defaults (quick keys and number tags Off), like Add to Favorites. A department never
loses its last channel or talkgroup, and a site its last frequency or a system its last site.

Pure functions, no Qt and no network.
"""
import copy
import re

import favorites_clipboard as fc
from rr_convert import SERVICE_TYPES

SERVICE_NAMES = {v: k.title().replace('Ems', 'EMS').replace('-Tac', '-Tac') for k, v in SERVICE_TYPES.items()}
GROUPS = [
    ('tg_names', 'Talkgroup names'),
    ('tg_settings', 'Talkgroup service type and timeslot'),
    ('tg_new', 'New talkgroups on RadioReference'),
    ('tg_gone', 'Talkgroups no longer on RadioReference (or now fully encrypted)'),
    ('freq_new', 'Site frequencies added on RadioReference'),
    ('freq_gone', 'Site frequencies no longer on RadioReference'),
    ('site_settings', 'Site NAC, channel numbers and colour codes'),
    ('site_new', 'New sites on RadioReference'),
    ('site_gone', 'Sites not on RadioReference'),
    ('ch_names', 'Channel names'),
    ('ch_settings', 'Channel modulation, tone and service type'),
    ('ch_new', 'New channels on RadioReference'),
    ('ch_gone', 'Channels no longer on RadioReference'),
]
GROUP_TITLES = dict(GROUPS)


class UpdateError(ValueError):
    """The two systems can't be compared; the text says why."""


def _col(row, i):
    return row[i].strip() if len(row) > i else ''


def mhz(hz):
    try:
        return f'{int(hz) / 1e6:.4f}'
    except (TypeError, ValueError):
        return str(hz)


def service_name(value):
    return SERVICE_NAMES.get(str(value).strip(), f'type {value}' if value else '—')


def audio_text(value):
    """'TONE=C107.2' → 'CTCSS 107.2', 'TONE=D023' → 'DCS 023', 'NAC=293' → 'NAC 293', 'ColorCode=1' →
    'colour code 1', '' → 'none'."""
    text = str(value or '').strip()
    m = re.fullmatch(r'TONE=C([\d.]+)', text)
    if m:
        return f'CTCSS {m.group(1)}'
    m = re.fullmatch(r'TONE=D(\d+)', text)
    if m:
        return f'DCS {m.group(1)}'
    for prefix, word in (('NAC=', 'NAC'), ('ColorCode=', 'colour code'), ('RAN=', 'RAN'), ('TONE=', 'tone')):
        if text.startswith(prefix):
            return f'{word} {text[len(prefix):]}'
    return text or 'none'


def placeholder(name, number=''):
    """True for a name nobody chose: empty, a bare number, 'TGID 1234' or the frequency itself."""
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    if not text:
        return True
    if re.fullmatch(r'(?i)(tgid|tg|talkgroup)?\s*:?\s*\d+', text):
        return True
    if number and text.replace(' MHz', '') in (str(number), mhz(number)):
        return True
    return False


def _leaves(records, kind):
    """[(index, department index, row)] of C-Freq or TGID rows, with the department each is in."""
    out, dept = [], None
    for i, row in enumerate(records):
        k = fc.kind_of(row)
        if k in fc.DEPARTMENTS or k == 'Site':
            dept = i if k in fc.DEPARTMENTS else None
        elif k == kind:
            out.append((i, dept, row))
    return out


def _sites(records):
    """{casefolded name: (start, end)} and the order of the names."""
    found = {}
    for kind, start, end in fc.blocks(records):
        if kind == 'Site':
            found.setdefault(_col(records[start], 3).casefold(), (start, end))
    return found


def _site_freqs(records, start, end):
    return [(i, records[i]) for i in range(start + 1, end) if fc.kind_of(records[i]) == 'T-Freq']


def _change(changes, group, text, default, **ops):
    change = {'id': f'{group}:{len(changes)}', 'group': group, 'text': text, 'default': bool(default),
              'sets': ops.get('sets', []), 'remove': ops.get('remove', []), 'add_freq': ops.get('add_freq', []),
              'add_blocks': ops.get('add_blocks', [])}
    changes.append(change)
    return change


def _match_sites(mine, rr_records, theirs, records):
    """{my site key: their site key}: same name first, then the RadioReference site with most frequencies
    in common (at least half of mine), so a site renamed in the list still matches."""
    pairs = {k: k for k in mine if k in theirs}
    used = set(pairs.values())
    for key, (s, e) in mine.items():
        if key in pairs:
            continue
        have = {_col(r, 5) for _i, r in _site_freqs(records, s, e)}
        best, score = None, 0
        for other, (os_, oe) in theirs.items():
            if other in used:
                continue
            common = len(have & {_col(r, 5) for _i, r in _site_freqs(rr_records, os_, oe)})
            if common > score:
                best, score = other, common
        if best is not None and have and score * 2 >= len(have):
            pairs[key] = best
            used.add(best)
    return pairs


def compare(records, rr_records):
    """Changes that would bring the list's system (records) in line with RadioReference's (rr_records).
    Both are the scanner's own rows: [Trunk | Conventional header, ...]."""
    if not records or not rr_records:
        raise UpdateError('Nothing to compare.')
    mine_kind, their_kind = fc.kind_of(records[0]), fc.kind_of(rr_records[0])
    if mine_kind != their_kind:
        raise UpdateError(f'{fc.system_name(records)} is a {mine_kind.lower()} system, but the RadioReference '
                          f'system {fc.system_name(rr_records)} is {their_kind.lower()}. Choose the matching system.')
    if mine_kind == 'Trunk' and fc.system_type(records) != fc.system_type(rr_records):
        raise UpdateError(f'{fc.system_name(records)} is a {fc.system_type(records)} system, but the RadioReference '
                          f'system {fc.system_name(rr_records)} is written as {fc.system_type(rr_records)}. '
                          'Talkgroup IDs are written differently for each type, so they can\'t be compared.')
    changes = []
    if mine_kind == 'Trunk':
        _compare_talkgroups(records, rr_records, changes)
        _compare_sites(records, rr_records, changes)
    else:
        _compare_channels(records, rr_records, changes)
    order = [g for g, _t in GROUPS]
    changes.sort(key=lambda c: order.index(c['group']))
    return changes


def _dept_name(records, index):
    return _col(records[index], 3) if index is not None else ''


def _compare_talkgroups(records, rr_records, changes):
    mine = {}
    for i, dept, row in _leaves(records, 'TGID'):
        mine.setdefault(_col(row, 5), []).append((i, dept, row))
    theirs = {}
    for i, dept, row in _leaves(rr_records, 'TGID'):
        theirs.setdefault(_col(row, 5), (i, dept, row))
    my_departments = {_col(records[s], 3).casefold() for k, s, _e in fc.blocks(records) if k == 'T-Group'}
    dmr = fc.system_type(records) == 'DmrOneFrequency'
    for tgid, places in mine.items():
        if tgid not in theirs:
            for i, dept, row in places:
                _change(changes, 'tg_gone', f'Delete {_col(row, 3)} (TGID {tgid}) from {_dept_name(records, dept)}',
                        False, remove=[(i, 'TGID', 5, tgid)])
            continue
        _ri, _rd, rr_row = theirs[tgid]
        for i, dept, row in places:
            new_name, old_name = _col(rr_row, 3), _col(row, 3)
            if new_name and new_name != old_name:
                _change(changes, 'tg_names', f'TGID {tgid}: {old_name or "(no name)"} → {new_name}',
                        placeholder(old_name, tgid), sets=[(i, 'TGID', 5, tgid, 3, new_name)])
            sets, words = [], []
            if _col(rr_row, 7) and _col(rr_row, 7) != _col(row, 7):
                sets.append((i, 'TGID', 5, tgid, 7, _col(rr_row, 7)))
                words.append(f'service {service_name(_col(row, 7))} → {service_name(_col(rr_row, 7))}')
            if dmr and _col(rr_row, 16) in ('1', '2') and _col(rr_row, 16) != _col(row, 16):
                sets.append((i, 'TGID', 5, tgid, 16, _col(rr_row, 16)))
                words.append(f'timeslot {_col(row, 16) or "Any"} → {_col(rr_row, 16)}')
            if sets:
                _change(changes, 'tg_settings', f'{old_name} (TGID {tgid}): ' + '; '.join(words), True, sets=sets)
    for tgid, (i, dept, rr_row) in theirs.items():
        if tgid in mine:
            continue
        department = _dept_name(rr_records, dept)
        into = department.casefold() in my_departments
        _change(changes, 'tg_new', f'Add {_col(rr_row, 3)} (TGID {tgid}, {service_name(_col(rr_row, 7))}) to '
                f'{department}' + ('' if into else ' (new department)'), into,
                add_blocks=[('dept', copy.deepcopy(rr_records[dept]), copy.deepcopy(rr_row))])


def _compare_sites(records, rr_records, changes):
    mine, theirs = _sites(records), _sites(rr_records)
    pairs = _match_sites(mine, rr_records, theirs, records)
    p25 = fc.system_type(records) in ('P25Standard', 'P25OneFrequency')
    for key, (s, e) in mine.items():
        site = _col(records[s], 3)
        if key not in pairs:
            _change(changes, 'site_gone', f'Delete site {site} (not found on RadioReference)', False,
                    remove=[(s, 'Site', 3, _col(records[s], 3))])
            continue
        rs, re_ = theirs[pairs[key]]
        rr_site = rr_records[rs]
        nac = _col(rr_site, 17)
        if p25 and nac and nac != 'Srch' and nac != _col(records[s], 17):
            _change(changes, 'site_settings', f'Site {site}: NAC {_col(records[s], 17) or "—"} → {nac}', True,
                    sets=[(s, 'Site', 3, _col(records[s], 3), 17, nac)])
        my_freqs = {_col(r, 5): (i, r) for i, r in _site_freqs(records, s, e)}
        rr_freqs = {_col(r, 5): r for _i, r in _site_freqs(rr_records, rs, re_)}
        for f, row in rr_freqs.items():
            if f not in my_freqs:
                lcn = _col(row, 6)
                _change(changes, 'freq_new', f'Site {site}: add {mhz(f)} MHz' +
                        (f' (LCN {lcn})' if lcn not in ('', '0') else ''), True,
                        add_freq=[(_col(records[s], 3), copy.deepcopy(row))])
                continue
            i, mine_row = my_freqs[f]
            sets, words = [], []
            lcn = _col(row, 6)
            if lcn not in ('', '0') and lcn != _col(mine_row, 6):
                sets.append((i, 'T-Freq', 5, f, 6, lcn))
                words.append(f'LCN {_col(mine_row, 6) or "—"} → {lcn}')
            code = _col(row, 7)
            if code and code != 'Srch' and code != _col(mine_row, 7):
                sets.append((i, 'T-Freq', 5, f, 7, code))
                words.append(f'{"RAN" if code.startswith("RAN") else "colour code"} {_col(mine_row, 7) or "—"} → {code}')
            if sets:
                _change(changes, 'site_settings', f'Site {site}, {mhz(f)} MHz: ' + '; '.join(words), True, sets=sets)
        for f, (i, row) in my_freqs.items():
            if f not in rr_freqs:
                _change(changes, 'freq_gone', f'Site {site}: delete {mhz(f)} MHz', True,
                        remove=[(i, 'T-Freq', 5, f)])
    used = set(pairs.values())
    for key, (rs, re_) in theirs.items():
        if key in used:
            continue
        count = len(_site_freqs(rr_records, rs, re_))
        _change(changes, 'site_new', f'Add site {_col(rr_records[rs], 3)} ({count} frequenc{"y" if count == 1 else "ies"})',
                False, add_blocks=[('site', copy.deepcopy(rr_records[rs:re_]), None)])


def _compare_channels(records, rr_records, changes):
    mine = _leaves(records, 'C-Freq')
    theirs = _leaves(rr_records, 'C-Freq')
    my_departments = {_col(records[s], 3).casefold() for k, s, _e in fc.blocks(records) if k == 'C-Group'}
    pairs, left_mine, left_theirs = [], list(mine), list(theirs)
    for m in list(left_mine):                            # same frequency and tone first
        hit = next((t for t in left_theirs if (_col(t[2], 5), _col(t[2], 7)) == (_col(m[2], 5), _col(m[2], 7))), None)
        if hit:
            pairs.append((m, hit))
            left_mine.remove(m)
            left_theirs.remove(hit)
    for m in list(left_mine):                            # then the same frequency, when it's the only one each side
        f = _col(m[2], 5)
        a = [x for x in left_mine if _col(x[2], 5) == f]
        b = [x for x in left_theirs if _col(x[2], 5) == f]
        if len(a) == 1 and len(b) == 1:
            pairs.append((m, b[0]))
            left_mine.remove(m)
            left_theirs.remove(b[0])
    for (i, dept, row), (_ri, _rd, rr_row) in pairs:
        f = _col(row, 5)
        old_name, new_name = _col(row, 3), _col(rr_row, 3)
        if new_name and new_name != old_name:
            _change(changes, 'ch_names', f'{mhz(f)} MHz: {old_name or "(no name)"} → {new_name}',
                    placeholder(old_name, f), sets=[(i, 'C-Freq', 5, f, 3, new_name)])
        sets, words = [], []
        for col, word in ((6, 'modulation'), (7, 'tone'), (8, 'service')):
            new, old = _col(rr_row, col), _col(row, col)
            if new == old or (col == 8 and not new):
                continue
            sets.append((i, 'C-Freq', 5, f, col, new))
            if col == 8:
                words.append(f'service {service_name(old)} → {service_name(new)}')
            elif col == 7:
                words.append(f'tone {audio_text(old)} → {audio_text(new)}')
            else:
                words.append(f'{word} {old or "none"} → {new or "none"}')
        if sets:
            _change(changes, 'ch_settings', f'{old_name} ({mhz(f)} MHz): ' + '; '.join(words), True, sets=sets)
    for i, dept, row in left_theirs:
        department = _dept_name(rr_records, dept)
        into = department.casefold() in my_departments
        _change(changes, 'ch_new', f'Add {_col(row, 3)} ({mhz(_col(row, 5))} MHz'
                + (f', {audio_text(_col(row, 7))}' if _col(row, 7) else '') + f') to {department}'
                + ('' if into else ' (new department)'), into,
                add_blocks=[('dept', copy.deepcopy(rr_records[dept]), copy.deepcopy(row))])
    for i, dept, row in left_mine:
        _change(changes, 'ch_gone', f'Delete {_col(row, 3)} ({mhz(_col(row, 5))} MHz) from {_dept_name(records, dept)}',
                False, remove=[(i, 'C-Freq', 5, _col(row, 5))])


# ---- applying ---------------------------------------------------------------------------------------
def _verify(records, index, kind, key_col, key):
    return 0 <= index < len(records) and fc.kind_of(records[index]) == kind and _col(records[index], key_col) == key


def plan_removals(records, chosen):
    """(removable [(index, kind, key_col, key)], kept [(text, why)]): never the last channel or talkgroup of a
    department, the last frequency of a site (counting frequencies being added), or the last site."""
    removing = {}
    for change in chosen:
        for item in change['remove']:
            removing[item[0]] = (item, change['text'])
    adding_to = {}
    for change in chosen:
        for site_name, _row in change['add_freq']:
            adding_to[site_name.casefold()] = adding_to.get(site_name.casefold(), 0) + 1
    ok, kept = set(), []
    blocks = fc.blocks(records)
    sites = [b for b in blocks if b[0] == 'Site']
    site_starts_removed = {i for i, (item, _t) in removing.items() if item[1] == 'Site'}
    if sites and len(site_starts_removed) >= len(sites):
        last = max(site_starts_removed)
        site_starts_removed.discard(last)
        kept.append((removing[last][1], 'a trunked system keeps at least one site'))
    ok |= site_starts_removed
    for kind, start, end in blocks:
        if kind == 'Site' and start in site_starts_removed:
            continue
        leaf = 'T-Freq' if kind == 'Site' else fc.LEAF_OF.get(kind)
        inside = [i for i in range(start + 1, end) if fc.kind_of(records[i]) == leaf]
        going = [i for i in inside if i in removing]
        if not going:
            continue
        extra = adding_to.get(_col(records[start], 3).casefold(), 0) if kind == 'Site' else 0
        if len(going) == len(inside) and not extra:
            keep = going[-1]
            going = going[:-1]
            what = 'frequency of its site' if kind == 'Site' else 'channel or talkgroup of its department'
            kept.append((removing[keep][1], f'it is the last {what}'))
        ok |= set(going)
    removable = [removing[i][0] for i in sorted(ok)]
    return removable, kept


def apply(entries, entry_index, chosen):
    """Make the chosen changes in entries[entry_index]. Returns {'done': n, 'kept': [(text, why)],
    'added': n}. Positions were worked out by compare() on these same rows; each is checked before use."""
    entry = entries[entry_index]
    records = entry['records']
    report = {'done': 0, 'kept': [], 'added': 0}
    for change in chosen:                                            # 1. values, in place
        applied = False
        for index, kind, key_col, key, col, value in change['sets']:
            if _verify(records, index, kind, key_col, key):
                row = records[index]
                while len(row) <= col:
                    row.append('')
                row[col] = value
                applied = True
        report['done'] += applied
    removable, kept = plan_removals(records, chosen)                  # 2. deletions, bottom up
    report['kept'] += kept
    sites = {b[1]: b for b in fc.blocks(records) if b[0] == 'Site'}
    for index, kind, key_col, key in sorted(removable, key=lambda r: -r[0]):
        if not _verify(records, index, kind, key_col, key):
            continue
        if kind == 'Site':
            _kind, start, end = sites[index]
            del records[start:end]
        else:
            del records[index]
        report['done'] += 1
    for change in chosen:                                            # 3. site frequencies
        for site_name, row in change['add_freq']:
            block = next((b for b in fc.blocks(records) if b[0] == 'Site'
                          and _col(records[b[1]], 3).casefold() == site_name.casefold()), None)
            if block is None:
                report['kept'].append((change['text'], 'the site is no longer in the list'))
                continue
            freqs = [i for i in range(block[1] + 1, block[2]) if fc.kind_of(records[i]) == 'T-Freq']
            at = (freqs[-1] + 1) if freqs else block[2]
            records.insert(at, copy.deepcopy(row))
            report['done'] += 1
            report['added'] += 1
    clip_records = [copy.deepcopy(records[0])]                       # 4. new sites, departments and leaves
    departments = {}
    for change in chosen:
        for what, head, leaf in change['add_blocks']:
            if what == 'site':
                clip_records.extend(copy.deepcopy(head))
            else:
                key = (fc.kind_of(head), _col(head, 3).casefold())
                if key not in departments:
                    departments[key] = [copy.deepcopy(head)]
                departments[key].append(copy.deepcopy(leaf))
    for rows in departments.values():
        clip_records.extend(rows)
    if len(clip_records) > 1:
        meta = entries[0]
        clip = {'what': 'system', 'name': fc.system_name(records), 'records': clip_records,
                'preamble': copy.deepcopy(meta.get('records', [])), 'encoding': meta.get('encoding', 'cp1252')}
        result = fc.paste(entries, clip, (entry_index, None), 'free')
        report['added'] += result['added'] + sum(len(_site_freqs(clip_records, s, e))
                                                 for k, s, e in fc.blocks(clip_records) if k == 'Site'
                                                 and _col(clip_records[s], 3) in result['sites'])
        report['done'] += result['added'] + len(result['sites'])
        report['clashes'] = result.get('clashes', [])
    fc._note_selection(entry)
    return report


def summary(changes):
    """Counts per group, for the window's heading."""
    counts = {}
    for change in changes:
        counts[change['group']] = counts.get(change['group'], 0) + 1
    return [(group, GROUP_TITLES[group], counts[group]) for group, _t in GROUPS if group in counts]
