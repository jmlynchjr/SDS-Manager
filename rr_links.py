# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Which RadioReference system each system in a Favorites List came from (v0.1.35).

Kept in the data folder as rr-links.json, so Update from RadioReference knows where to look next time:

    {"<configuration folder>": {"<list file>": {"<Trunk|Conventional>:<type>:<system name>":
        {"key": ["trs", 6060], "label": "Palmetto 800", "state": 45, "county": null}}}}

Only RadioReference's own IDs and the name are kept, never RadioReference data. A link is written when a system
is added from RadioReference (Add to Favorites, a new list) or chosen in the update window. Renaming a system
in the list just means choosing its RadioReference system again once.
"""
import json
from pathlib import Path

import data_area

FILE_NAME = 'rr-links.json'
KINDS = ('trs', 'county', 'agency', 'hpdb')       # hpdb: a Uniden database state file (personal build)


def path(area=None):
    return Path(area or data_area.AREA) / FILE_NAME


def system_key(records):
    """'Trunk:P25Standard:palmetto 800' for a system's header row."""
    head = records[0] if records else []
    kind = head[0].strip() if head else ''
    sys_type = head[6].strip() if kind == 'Trunk' and len(head) > 6 else kind
    name = ' '.join(head[3].split()).casefold() if len(head) > 3 else ''
    return f'{kind}:{sys_type}:{name}'


def parse_source(source):
    """('trs', 6060) from Database Contents' 'rr:trs:6060', or None."""
    parts = str(source or '').split(':')
    if len(parts) == 3 and parts[0] == 'rr' and parts[1] in KINDS and parts[2].isdigit():
        return parts[1], int(parts[2])
    return None


def load(area=None):
    try:
        data = json.loads(path(area).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data, area=None):
    target = path(area)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding='utf-8')
    tmp.replace(target)


def slot(records, source='rr'):
    """Where a system's link is kept: RadioReference links under the system's key, others (the Uniden
    database, v0.1.37) under the key and '@source', so a system can have one of each."""
    return system_key(records) + ('' if source == 'rr' else '@' + source)


def get(configuration, list_file, records, area=None, source='rr'):
    """The link for a system, {'key': (kind, id), 'label', 'state', 'county'}, or None."""
    link = load(area).get(str(configuration), {}).get(str(list_file), {}).get(slot(records, source))
    if not isinstance(link, dict):
        return None
    key = link.get('key')
    if not (isinstance(key, list) and len(key) == 2 and key[0] in KINDS and str(key[1]).isdigit()):
        return None
    return {'key': (key[0], int(key[1])), 'label': str(link.get('label') or ''),
            'state': link.get('state'), 'county': link.get('county')}


def remember(configuration, list_file, records, key, label='', state=None, county=None, area=None, source='rr'):
    if not configuration or not list_file or not records or key is None:
        return
    data = load(area)
    data.setdefault(str(configuration), {}).setdefault(str(list_file), {})[slot(records, source)] = {
        'key': [key[0], int(key[1])], 'label': str(label), 'state': state, 'county': county}
    save(data, area)


def forget(configuration, list_file, records, area=None, source='rr'):
    data = load(area)
    systems = data.get(str(configuration), {}).get(str(list_file), {})
    if systems.pop(slot(records, source), None) is not None:
        save(data, area)
