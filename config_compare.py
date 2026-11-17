# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Compare the open configuration with the scanner (v0.1.32), or two saved configurations or scanner backups
(v0.1.38). Read only; no Qt.

Answers "what is different between what I have here and what is on the scanner?" at the level you
work at, not file by file:

- Favorites Lists, matched by file name: on both and the same, on both but different, only in the
  configuration (Export would add it), only on the scanner;
- inside a list that differs: every system, site, department, channel, talkgroup and site frequency
  added, removed or changed, with the fields that differ (old → new). Lines are matched by where they
  are (system › department › name and frequency or TGID), like scanner_avoids, because the scanner
  leaves the record ID columns empty;
- Favorites List settings in f_list.cfg (name, quick key, number tag, startup keys, …) and the list order;
- scanner settings in profile.cfg (global, search, weather, display, hardware, …);
- discovery.cfg, and the date of each master database (HPDB/), for information.

Avoid differences are marked "changed on the scanner" when SDS-Manager knows the avoids at the time the
two last matched (export-state.json). Nothing is written, on the scanner or in the configuration.
"""
from pathlib import Path

SYSTEMS = ('Conventional', 'Trunk')
GROUPS = ('Site', 'C-Group', 'T-Group')
LEAVES = ('C-Freq', 'TGID', 'T-Freq')
WORDS = {'Conventional': 'conventional system', 'Trunk': 'trunked system', 'Site': 'site',
         'C-Group': 'department', 'T-Group': 'department', 'C-Freq': 'channel', 'TGID': 'talkgroup',
         'T-Freq': 'site frequency'}
# Field names, 0-based. Leaves follow the SDS Series File Specification v2.00; the rest were checked
# against real scanner files (test_fixtures). Anything else is shown as "field N" (1-based, like the spec).
COMMON = {3: 'Name', 4: 'Avoid'}
LABELS = {
    'C-Freq': {5: 'Frequency', 6: 'Modulation', 7: 'Audio Option', 8: 'Service Type', 9: 'Attenuator',
               10: 'Delay', 11: 'Volume Offset', 12: 'Alert Tone', 13: 'Alert Volume', 14: 'Alert Color',
               15: 'Alert Pattern', 16: 'Number Tag', 17: 'Priority'},
    'TGID': {5: 'TGID', 6: 'Audio Type', 7: 'Service Type', 8: 'Delay', 9: 'Volume Offset', 10: 'Alert Tone',
             11: 'Alert Volume', 12: 'Alert Color', 13: 'Alert Pattern', 14: 'Number Tag', 15: 'Priority',
             16: 'TDMA Slot'},
    'T-Freq': {5: 'Frequency', 6: 'LCN', 7: 'Colour Code / RAN / Area'},
    'Site': {5: 'Latitude', 6: 'Longitude', 7: 'Range'},
    'C-Group': {5: 'Latitude', 6: 'Longitude', 7: 'Range', 8: 'Location Type'},
    'T-Group': {5: 'Latitude', 6: 'Longitude', 7: 'Range', 8: 'Location Type'},
    'Trunk': {6: 'System Type'},
    'Conventional': {6: 'System Type'},
}
IGNORED = (1, 2)            # MyId and ParentId of named records: the scanner leaves them empty
AVOIDS = {'Off': 'Off', 'Temporary': 'Temporary Avoid', 'On': 'Permanent Avoid'}
OTHER_FILES = ('discovery.cfg',)
# The words for the two sides. Internally the first side is always "configuration" (what you would have) and
# the second "scanner" (what you compare it with); v0.1.38 compares two saved configurations or backups too.
SCANNER_SIDES = {
    'title': 'COMPARE CONFIGURATION WITH SCANNER — READ ONLY',
    'Old': 'Scanner', 'New': 'Configuration', 'old': 'the scanner', 'new': 'the configuration',
    'in_old': 'only on the scanner', 'in_new': 'only in the configuration',
    'same': 'The scanner matches this configuration.', 'differ': 'The scanner and this configuration differ.',
    'old_line': 'Scanner folder', 'new_line': 'Configuration',
    'arrow': 'In the lines below, "scanner → configuration" shows what Export to Scanner would change.',
    'mode': 'scanner',
}


def configuration_sides(first, second):
    """Words for comparing two saved configurations (or backups): first is what you'd have, second the other."""
    return {
        'title': 'COMPARE TWO CONFIGURATIONS — READ ONLY',
        'Old': second, 'New': first, 'old': second, 'new': first,
        'in_old': f'only in {second}', 'in_new': f'only in {first}',
        'same': f'{first} and {second} are the same.', 'differ': f'{first} and {second} differ.',
        'old_line': 'Compared with', 'new_line': 'Configuration',
        'arrow': f'In the lines below, "{second} → {first}" shows each value in {second}, then in {first}.',
        'mode': 'configurations',
    }


def cap(text):
    """First letter up, the rest as it is (names keep their capitals)."""
    return text[:1].upper() + text[1:]


def status_text(status, sides=None):
    sides = sides or SCANNER_SIDES
    return {'same': 'Same', 'different': 'Different', 'configuration only': cap(sides['in_new']),
            'scanner only': cap(sides['in_old']), 'unreadable': 'Could not be read'}.get(status, status)
MAX_BYTES = 25 * 1024 * 1024


# ---------------------------------------------------------------- reading
def _rows(raw):
    text = raw.decode('utf-8-sig') if raw.startswith(b'\xef\xbb\xbf') else raw.decode('cp1252', 'replace')
    return [line.split('\t') for line in text.splitlines() if line.strip()]


def _read(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('symbolic link rejected: ' + path.name)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(path.name + ' is larger than 25 MB')
    return path.read_bytes()


def _mhz(value):
    return '%.4f MHz' % (int(value) / 1e6) if value.isdecimal() and value != '0' else value


def _service(value):
    try:
        from favorites_settings_window import SERVICE_TYPE_NAMES
        return SERVICE_TYPE_NAMES.get(value, value)
    except Exception:                        # the window needs Qt; the names are a nicety
        return value


def shown(kind, index, value):
    """A field value as the user knows it."""
    label = field_label(kind, index)
    if value == '':
        return '(blank)'
    if label == 'Frequency':
        return _mhz(value)
    if label == 'Avoid':
        return AVOIDS.get(value, value)
    if label == 'Service Type':
        return _service(value)
    return value


def field_label(kind, index):
    return LABELS.get(kind, {}).get(index) or (COMMON.get(index) if kind in SYSTEMS + GROUPS + LEAVES[:2]
                                                else None) or 'field %d' % (index + 1)


def entries(raw):
    """{key: {'kind', 'label', 'row', 'order'}} of every line below the header, keyed by where it is."""
    found, seen = {}, {}
    system = group = ''
    system_name = group_name = ''
    for order, row in enumerate(_rows(raw)):
        kind = row[0].strip()
        if kind in ('TargetModel', 'FormatVersion') or not kind:
            continue
        name = row[3].strip() if len(row) > 3 else ''
        value = row[5].strip() if len(row) > 5 else ''
        if kind in SYSTEMS:
            system, group, system_name, group_name = f'{kind}:{name}', '', name, ''
            path, label = system, name
        elif kind in GROUPS:
            group, group_name = f'{kind}:{name}', name
            path, label = f'{system} / {group}', f'{system_name} › {name}'
        elif kind in LEAVES:
            path = f'{system} / {group} / {kind}:{name}={value}'
            what = _mhz(value) if kind != 'TGID' else 'TGID ' + value
            label = f'{system_name} › {group_name} › ' + (f'{name} ({what})' if name else what)
        else:                                   # DQKs_Status, BandPlan, Rectangle, AreaState, …
            parent = f'{system} / {group}' if group else system
            path = f'{parent} / {kind}'
            label = ' › '.join(x for x in (system_name, group_name) if x) + f' › {kind}'
        seen[path] = seen.get(path, 0) + 1
        key = path if seen[path] == 1 else f'{path} #{seen[path]}'
        if seen[path] > 1 and kind not in SYSTEMS + GROUPS + LEAVES:
            label += ' #%d' % seen[path]
        found[key] = {'kind': kind, 'label': label, 'row': row, 'order': order}
    return found


def _counts(items):
    counts = {}
    for item in items.values():
        word = WORDS.get(item['kind'])
        if word:
            counts[word] = counts.get(word, 0) + 1
    return counts


def field_changes(kind, old_row, new_row):
    """[(label, scanner value, configuration value)] for the fields that differ."""
    out = []
    named = kind in SYSTEMS + GROUPS + ('C-Freq', 'TGID')
    for index in range(1, max(len(old_row), len(new_row))):
        if named and index in IGNORED:
            continue
        old = old_row[index] if index < len(old_row) else ''
        new = new_row[index] if index < len(new_row) else ''
        if old.strip() != new.strip():
            out.append((field_label(kind, index), shown(kind, index, old), shown(kind, index, new)))
    return out


def compare_list(scanner_raw, configuration_raw):
    """{'added': [...], 'removed': [...], 'changed': [...], 'moved': bool, 'counts': (scanner, config)}.

    'added' = only in the configuration, 'removed' = only on the scanner."""
    theirs, mine = entries(scanner_raw), entries(configuration_raw)
    added = [{'key': k, 'kind': v['kind'], 'label': v['label']} for k, v in mine.items() if k not in theirs]
    removed = [{'key': k, 'kind': v['kind'], 'label': v['label']} for k, v in theirs.items() if k not in mine]
    changed = []
    for key, item in mine.items():
        if key in theirs:
            fields = field_changes(item['kind'], theirs[key]['row'], item['row'])
            if fields:
                changed.append({'key': key, 'kind': item['kind'], 'label': item['label'], 'fields': fields})
    common = [k for k in mine if k in theirs]
    moved = common != sorted(common, key=lambda k: theirs[k]['order'])
    return {'added': added, 'removed': removed, 'changed': changed, 'moved': moved,
            'counts': (_counts(theirs), _counts(mine))}


# ---------------------------------------------------------------- whole configuration
def _index(path):
    try:
        import flist_settings
        return flist_settings.read_lists(_read(path)) if Path(path).is_file() else []
    except (OSError, ValueError, UnicodeError):
        return []


def _setting_lines(old_lists, new_lists):
    """f_list.cfg differences for lists on both, in plain words."""
    import flist_settings
    names = {l['filename'].lower() for l in new_lists}
    old = [l for l in old_lists if l['filename'].lower() in names]
    by_name = {l['filename'].lower(): l for l in new_lists}
    new = [by_name[l['filename'].lower()] for l in old]
    try:
        edits = flist_settings.edits_between(old, new)
        lines = flist_settings.describe(old, edits)
    except (ValueError, KeyError):
        return {}
    per_list = {}
    for (filename, _position), line in zip(sorted(edits, key=lambda k: (k[0], k[1])), lines):
        per_list.setdefault(filename.lower(), []).append(line.split(' — ', 1)[-1])
    return per_list


def _profile_lines(scanner_path, configuration_path, sides=None):
    sides = sides or SCANNER_SIDES
    if not scanner_path.is_file() or not configuration_path.is_file():
        missing = sides['old'] if not scanner_path.is_file() else sides['new']
        return [], 'profile.cfg is missing from ' + missing
    old, new = _read(scanner_path), _read(configuration_path)
    if old == new:
        return [], ''
    import profile_schema
    try:
        edits = profile_schema.diff_sections(old, new)
        lines = list(profile_schema.describe(old, edits))
    except (ValueError, KeyError, IndexError) as exc:
        return [], 'profile.cfg differs in a way that cannot be listed setting by setting (%s)' % exc
    if not lines:
        return [], 'profile.cfg differs only outside the settings SDS-Manager edits'
    return lines, ''


def _database_date(folder):
    try:
        from scanner_detect import _read_first
        fields = _read_first(Path(folder) / 'HPDB' / 'hpdb.cfg', 'DateModified')
        return fields[1].strip() if fields and len(fields) > 1 else ''
    except Exception:
        return ''


def _avoid_notes(configuration, scanner):
    """{(filename, label): 'changed on the scanner' | 'changed in SDS-Manager'} for avoid differences."""
    try:
        import export_state
        import scanner_avoids
        found = scanner_avoids.differences(configuration, scanner, export_state.matched_avoids(configuration))
    except Exception:
        return {}
    words = {'scanner': 'changed on the scanner', 'SDS-Manager': 'changed in SDS-Manager'}
    return {(f['file'].lower(), f['key']): words[f['made_on']] for f in found if f['made_on'] in words}


def compare(configuration, scanner, sides=None):
    """Compare a saved configuration folder with the scanner's BCDx36HP folder. Never writes.
    With sides (configuration_sides), "scanner" is another saved configuration or a scanner backup (v0.1.38)."""
    sides = sides or SCANNER_SIDES
    configuration = Path(configuration)
    local, scanner = configuration / 'BCDx36HP', Path(scanner)
    if scanner.name.lower() != 'bcdx36hp':
        scanner = scanner / 'BCDx36HP'
    if not (scanner / 'favorites_lists').is_dir():
        raise ValueError(('The scanner' if sides['mode'] == 'scanner' else sides['Old'])
                         + ' has no BCDx36HP/favorites_lists folder.')
    if not (local / 'favorites_lists').is_dir():
        raise ValueError('The configuration has no Favorites Lists.')
    mine_index = _index(local / 'favorites_lists' / 'f_list.cfg')
    their_index = _index(scanner / 'favorites_lists' / 'f_list.cfg')
    mine_names = {l['filename'].lower(): l['name'] for l in mine_index}
    their_names = {l['filename'].lower(): l['name'] for l in their_index}
    mine_files = {p.name.lower(): p for p in (local / 'favorites_lists').glob('*.hpd')}
    their_files = {p.name.lower(): p for p in (scanner / 'favorites_lists').glob('*.hpd')}
    settings = _setting_lines(their_index, mine_index)
    notes = _avoid_notes(configuration, scanner) if sides['mode'] == 'scanner' else {}
    order = [l['filename'].lower() for l in mine_index]
    order += sorted(set(mine_files) - set(order))
    order += [l['filename'].lower() for l in their_index if l['filename'].lower() not in order]
    order += sorted(set(their_files) - set(order))
    lists = []
    for filename in order:
        if filename not in mine_files and filename not in their_files:
            continue
        item = {'filename': filename, 'name': mine_names.get(filename) or their_names.get(filename) or filename,
                'settings': settings.get(filename, []), 'error': ''}
        try:
            if filename not in their_files:
                item['status'] = 'configuration only'
                item['counts'] = ({}, _counts(entries(_read(mine_files[filename]))))
            elif filename not in mine_files:
                item['status'] = 'scanner only'
                item['counts'] = (_counts(entries(_read(their_files[filename]))), {})
            else:
                theirs, mine = _read(their_files[filename]), _read(mine_files[filename])
                result = compare_list(theirs, mine)
                for change in result['changed']:
                    note = notes.get((filename, change['key']))
                    if note:
                        change['fields'] = [(l, o, n + (' (%s)' % note if l == 'Avoid' else ''))
                                            for l, o, n in change['fields']]
                item.update(result)
                same = not (result['added'] or result['removed'] or result['changed'] or result['moved'])
                if same and theirs != mine:
                    item['note'] = 'Same content; the files differ only in spacing, ID columns or line endings.'
                item['status'] = 'same' if same and not item['settings'] else 'different'
        except (OSError, ValueError, UnicodeError) as exc:
            item['status'], item['error'] = 'unreadable', str(exc)
        lists.append(item)
    common = [f for f in (l['filename'].lower() for l in mine_index) if f in their_names]
    their_common = [f for f in (l['filename'].lower() for l in their_index) if f in mine_names]
    profile, profile_note = _profile_lines(scanner / 'profile.cfg', local / 'profile.cfg', sides)
    others = []
    for name in OTHER_FILES:
        a, b = scanner / name, local / name
        if a.is_file() and b.is_file():
            others.append((name, 'same' if _read(a) == _read(b) else 'different'))
        elif a.is_file() or b.is_file():
            others.append((name, sides['in_old'] if a.is_file() else sides['in_new']))
    result = {'configuration': str(configuration), 'scanner': str(scanner), 'lists': lists,
              'order_changed': common != their_common, 'profile': profile, 'profile_note': profile_note,
              'other_files': others,
              'database': (_database_date(local), _database_date(scanner)), 'sides': sides}
    result['identical'] = (all(l['status'] == 'same' for l in lists) and not result['order_changed']
                           and not profile and not profile_note
                           and all(state == 'same' for _, state in others))
    return result


# ---------------------------------------------------------------- words
def _plural(n, word):
    if n == 1:
        return '1 ' + word
    return '%d %s' % (n, word[:-1] + 'ies' if word.endswith('y') else word + 's')


def count_text(counts):
    order = ('conventional system', 'trunked system', 'site', 'department', 'site frequency', 'channel',
             'talkgroup')
    return ', '.join(_plural(counts[k], k) for k in order if counts.get(k)) or 'empty'


def summary(result):
    """(headline, [short lines]) for the top of the window."""
    lists = result['lists']
    sides = result.get('sides') or SCANNER_SIDES
    tally = {}
    for l in lists:
        tally[l['status']] = tally.get(l['status'], 0) + 1
    if result['identical']:
        return sides['same'], []
    lines = []
    if tally.get('different'):
        lines.append(_plural(tally['different'], 'Favorites List') + (' differs' if tally['different'] == 1
                                                                      else ' differ'))
    if tally.get('configuration only'):
        lines.append(_plural(tally['configuration only'], 'Favorites List') + ' ' + sides['in_new'])
    if tally.get('scanner only'):
        lines.append(_plural(tally['scanner only'], 'Favorites List') + ' ' + sides['in_old'])
    if tally.get('unreadable'):
        lines.append(_plural(tally['unreadable'], 'Favorites List') + ' could not be read')
    if tally.get('same'):
        lines.append(_plural(tally['same'], 'Favorites List') + (' is' if tally['same'] == 1 else ' are')
                     + ' the same')
    if result['order_changed']:
        lines.append('Favorites List order differs')
    if result['profile']:
        lines.append(_plural(len(result['profile']), 'scanner setting') + (' differs' if len(result['profile']) == 1
                                                                          else ' differ'))
    elif result['profile_note']:
        lines.append(result['profile_note'])
    for name, state in result['other_files']:
        if state != 'same':
            lines.append(f'{name}: {state}')
    return sides['differ'], lines


def report_lines(result, configuration_name=''):
    """The whole comparison as plain text (Save Report / Copy)."""
    headline, short = summary(result)
    sides = result.get('sides') or SCANNER_SIDES
    other = result['scanner'] if sides['mode'] == 'scanner' else sides['Old']
    out = [sides['title'], '',
           sides['new_line'] + ': ' + (configuration_name or Path(result['configuration']).name),
           sides['old_line'] + ': ' + other, '', headline]
    out += ['  • ' + s for s in short]
    mine_db, their_db = result['database']
    if (mine_db or their_db) and sides['mode'] == 'scanner':
        out += ['', 'Master database: scanner %s, configuration copy %s (Export to Scanner never changes it; '
                'use Update Scanner\'s Master Database)' % (their_db or 'unknown', mine_db or 'unknown')]
    elif mine_db or their_db:
        out += ['', 'Master database: %s %s, %s %s' % (sides['Old'], their_db or 'unknown', sides['New'],
                                                        mine_db or 'unknown')]
    out.append('')
    out.append(sides['arrow'])
    for l in result['lists']:
        out += ['', '%s — %s (%s)' % (l['name'], status_text(l['status'], sides).upper(), l['filename'])]
        if l['error']:
            out.append('  Could not compare: ' + l['error'])
            continue
        scanner_counts, mine_counts = l.get('counts', ({}, {}))
        if l['status'] == 'configuration only':
            out.append('  %s: %s' % (cap(sides['in_new']), count_text(mine_counts)))
        elif l['status'] == 'scanner only':
            out.append('  %s: %s' % (cap(sides['in_old']), count_text(scanner_counts)))
        else:
            if scanner_counts != mine_counts:
                out.append('  %s: %s' % (sides['Old'], count_text(scanner_counts)))
                out.append('  %s: %s' % (sides['New'], count_text(mine_counts)))
            if l.get('note'):
                out.append('  ' + l['note'])
        for line in l['settings']:
            out.append('  List setting — ' + line)
        if l.get('moved'):
            out.append('  Entries are in a different order')
        for item in l.get('added', []):
            out.append('  + %s %s (%s)' % (WORDS.get(item['kind'], item['kind']).capitalize(), item['label'],
                                            sides['in_new']))
        for item in l.get('removed', []):
            out.append('  − %s %s (%s)' % (WORDS.get(item['kind'], item['kind']).capitalize(), item['label'],
                                            sides['in_old']))
        for item in l.get('changed', []):
            out.append('  ~ %s %s' % (WORDS.get(item['kind'], item['kind']).capitalize(), item['label']))
            for label, old, new in item['fields']:
                out.append('      %s: %s → %s' % (label, old, new))
    if result['order_changed']:
        out += ['', 'Favorites List order differs between %s and %s.' % (sides['old'], sides['new'])]
    if result['profile'] or result['profile_note']:
        out += ['', 'SCANNER SETTINGS (profile.cfg)']
        out += ['  ' + line for line in result['profile']]
        if result['profile_note']:
            out.append('  ' + result['profile_note'])
    for name, state in result['other_files']:
        out += ['', '%s: %s' % (name, state)]
    out += ['', 'Nothing was written to %s or %s.' % (sides['old'], sides['new'])]
    return out
