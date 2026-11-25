# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Tools → Check Heard Talkgroups with RadioReference… (v0.1.39).

SDS100 Monitor writes every reception to ~/SDS100Monitor/history (System, Channel, Talkgroup …). Talkgroups heard
there that aren't in the open configuration's Favorites Lists, or are in them with no real name (blank, the ID,
"TGID 44353"), are looked up on RadioReference through the RadioReference system each list system is linked to
(rr_links, the same links as Update from RadioReference). The window shows RadioReference's name, category and
service type; Apply adds the missing ones (into a department named like the RadioReference category, made if
needed) and names the unnamed ones, as one Undo step. Save Configuration and Export to Scanner as usual.

The Monitor's files are only read. RadioReference is read live through your own account; nothing is stored.
Pure apart from reading the Monitor's files; no Qt.
"""
import csv
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import hand_entry
import monitor_link
import rr_convert

DAYS = 30
SERVICE_LABELS = {value: name.title().replace('Ems', 'EMS') for name, value in rr_convert.SERVICE_TYPES.items()}
FALLBACK_DEPARTMENT = 'Heard by Monitor'


def _fold(text):
    return ' '.join(str(text or '').split()).casefold()


def _tgid(text):
    value = re.sub(r'^(TGID|TG)\s*[:=]?\s*', '', str(text or '').strip(), flags=re.I)
    return (value.lstrip('0') or '0') if value.isdigit() else ''


# ---- what the Monitor heard ---------------------------------------------------------------------------
def heard_talkgroups(days=DAYS, data_dir=None, today=None):
    """{(system folded, tgid): {system, tgid, calls, seconds, last, shown}} from the Monitor's history of the
    last `days` days. `shown` is the name the scanner showed most often, when it was a real name."""
    folder = Path(data_dir or monitor_link.monitor_data_dir()) / 'history'
    today = today or date.today()
    first = today - timedelta(days=days - 1)
    heard, shown = {}, {}
    for path in sorted(folder.glob('reception_history_????-??-??.csv')) if folder.is_dir() else []:
        try:
            day = date.fromisoformat(path.stem[-10:])
        except ValueError:
            continue
        if not first <= day <= today:
            continue
        try:
            with path.open(newline='', encoding='utf-8-sig') as stream:
                reader = csv.reader(stream)
                if next(reader, None) != monitor_link.MONITOR_HISTORY_HEADERS:
                    continue
                for row in reader:
                    if len(row) != len(monitor_link.MONITOR_HISTORY_HEADERS):
                        continue
                    tgid = _tgid(row[7])
                    system = row[3].strip()
                    if not tgid or not system or system == '—':
                        continue
                    key = (_fold(system), tgid)
                    item = heard.setdefault(key, {'system': system, 'tgid': tgid, 'calls': 0, 'seconds': 0.0,
                                                  'last': '', 'shown': ''})
                    item['calls'] += 1
                    try:
                        item['seconds'] += float(row[2] or 0)
                    except ValueError:
                        pass
                    item['last'] = max(item['last'], row[0])
                    name = row[5].strip()
                    if name and name != '—' and not monitor_link.is_placeholder_name(name, tgid):
                        shown.setdefault(key, Counter())[name[:monitor_link.MAX_NAME]] += 1
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
    for key, names in shown.items():
        heard[key]['shown'] = names.most_common(1)[0][0]
    return heard


# ---- what the lists have ------------------------------------------------------------------------------
def list_index(drafts):
    """({(system folded, tgid): [location]}, {system folded: [(draft, entry index)]}) for the trunked systems
    of the open lists. A location is {draft, entry_index, row_index, department, name, placeholder}."""
    talkgroups, systems = {}, {}
    for draft, entries in drafts.items():
        for entry_index, entry in enumerate(entries or []):
            records = entry.get('records') or []
            if entry.get('scope') == 'metadata' or not records or records[0][0].strip() != 'Trunk':
                continue
            system = _fold(records[0][3] if len(records[0]) > 3 else '')
            systems.setdefault(system, []).append((draft, entry_index))
            department = ''
            for row_index, row in enumerate(records):
                kind = row[0].strip() if row else ''
                if kind == 'T-Group':
                    department = row[3] if len(row) > 3 else ''
                elif kind == 'TGID' and len(row) > 5 and row[5].strip().isdigit():
                    tgid = row[5].strip().lstrip('0') or '0'
                    talkgroups.setdefault((system, tgid), []).append({
                        'draft': draft, 'entry_index': entry_index, 'row_index': row_index, 'tgid': tgid,
                        'department': department, 'name': row[3],
                        'placeholder': monitor_link.is_placeholder_name(row[3], tgid)})
    return talkgroups, systems


def unknown_talkgroups(heard, drafts, min_calls=1):
    """Heard talkgroups that need something: [{..heard.., status, locations, systems}], most calls first.
    status: 'missing' (the system is in a list, the talkgroup isn't), 'unnamed' (in a list with no real name), or
    'no_system' (no trunked system of that name in the open lists, so it can't be added)."""
    talkgroups, systems = list_index(drafts)
    out = []
    for key, item in heard.items():
        if item['calls'] < min_calls:
            continue
        locations = talkgroups.get(key, [])
        if locations and not any(loc['placeholder'] for loc in locations):
            continue                                    # already in a list with a real name
        status = 'unnamed' if locations else ('missing' if key[0] in systems else 'no_system')
        out.append(dict(item, status=status, locations=[loc for loc in locations if loc['placeholder']],
                        systems=systems.get(key[0], [])))
    out.sort(key=lambda i: (i['status'] == 'no_system', -i['calls'], i['system'].casefold(), int(i['tgid'])))
    return out


# ---- RadioReference ----------------------------------------------------------------------------------
def _items(value):
    if value is None or value == '':
        return []
    return value if isinstance(value, list) else [value]


def rr_talkgroups(talkgroups, categories):
    """{tgid: {name, alpha, description, category, service, encrypted, partly_encrypted}} from getTrsTalkgroups and
    getTrsTalkgroupCats replies."""
    cat_names = {}
    for cat in _items(categories):
        if isinstance(cat, dict) and str(cat.get('tgCid', '')).strip():
            cat_names[str(cat['tgCid']).strip()] = str(cat.get('tgCname') or '').strip()
    out = {}
    for tg in _items(talkgroups):
        if not isinstance(tg, dict):
            continue
        tgid = str(tg.get('tgDec') or '').strip().lstrip('0') or ''
        if not tgid.isdigit():
            continue
        description, alpha = str(tg.get('tgDescr') or '').strip(), str(tg.get('tgAlpha') or '').strip()
        out[tgid] = {
            # The same choice of name as lists built from RadioReference (rr_convert.talkgroup_row).
            'name': rr_convert.clip(description or alpha, f'TGID {tgid}'),
            'alpha': alpha, 'description': description,
            'category': cat_names.get(str(tg.get('tgCid') or '').strip(), ''),
            'service': rr_convert.service_type(tg.get('tags')),
            # enc: 0 clear, 1 partly encrypted, 2 fully encrypted (as rr_convert reads it).
            'encrypted': str(tg.get('enc') or '0') == '2', 'partly_encrypted': str(tg.get('enc') or '0') == '1'}
    return out


def fetch_rr(browser, sid):
    """getTrsTalkgroups and getTrsTalkgroupCats for a system, through an RRBrowser (kept for this session)."""
    client = browser.client
    talkgroups = browser._get(('trs-tgs', sid), lambda: client.trs_talkgroups(sid))
    categories = browser._get(('trs-cats', sid), lambda: client.trs_talkgroup_cats(sid))
    return rr_talkgroups(talkgroups, categories)


def service_label(value):
    return SERVICE_LABELS.get(str(value), 'Other')


def suggested(item, info):
    """(name, department, tick) for a row: RadioReference first, then the name the scanner showed."""
    name = (info or {}).get('name') or item.get('shown') or ''
    department = (info or {}).get('category') or FALLBACK_DEPARTMENT
    tick = bool(info) and not info['encrypted'] and item['status'] != 'no_system'
    return name, department, tick


# ---- applying ----------------------------------------------------------------------------------------
def departments(records):
    """Talkgroup department names of a system, in list order."""
    return [row[3] for row in records if row and row[0].strip() == 'T-Group' and len(row) > 3]


def _department_end(records, start):
    return next((i for i in range(start + 1, len(records))
                 if records[i][0].strip() in ('T-Group', 'Site', 'Trunk', 'Conventional', 'C-Group')), len(records))


def add_talkgroup(records, tgid, name, department, service=rr_convert.OTHER):
    """Put a talkgroup into the named department of a system (made at the end of the system if it isn't there).
    Returns (row index, made a new department). Raises ValueError (hand_entry.EntryError) with a plain reason."""
    if any(r and r[0].strip() == 'TGID' and len(r) > 5 and (r[5].strip().lstrip('0') or '0') == tgid for r in records):
        raise ValueError(f'Talkgroup {tgid} is already in this system.')
    template = next((r for r in records if r and r[0].strip() == 'TGID'), None)
    row = hand_entry.talkgroup_row(template, name, tgid, service)
    wanted = _fold(department)
    start = next((i for i, r in enumerate(records) if r and r[0].strip() == 'T-Group' and len(r) > 3
                  and _fold(r[3]) == wanted), None)
    if start is not None:
        end = _department_end(records, start)
        records.insert(end, row)
        return end, False
    like = next((r for r in records if r and r[0].strip() == 'T-Group'), None)
    group = hand_entry.talkgroup_department_rows(department, [row], like)
    records.extend(group)
    return len(records) - 1, True


def apply(drafts, choices):
    """choices = [(item, name, department, service)]. Unnamed talkgroups get the name everywhere they are
    unnamed; missing ones are added to the first list with that system. Returns (named, added, new departments).
    Raises ValueError when a list changed since it was read, or a talkgroup can't be added."""
    named = added = made = 0
    for item, name, department, service in choices:
        name = ' '.join(str(name or '').split())
        if not name:
            raise ValueError(f'Talkgroup {item["tgid"]} ({item["system"]}) needs a name.')
        if item['status'] == 'unnamed':
            named += monitor_link.apply_names(drafts, [(loc, name) for loc in item['locations']])
        elif item['status'] == 'missing':
            draft, entry_index = item['systems'][0]
            records = drafts[draft][entry_index]['records']
            _row, new = add_talkgroup(records, item['tgid'], name, department or FALLBACK_DEPARTMENT, service)
            added += 1
            made += 1 if new else 0
    return named, added, made
