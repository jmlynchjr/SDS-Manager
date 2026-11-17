# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Import and export scan profiles (v0.1.33). Pure; no Qt.

A scan profile (keys_model.Model.profile) records which keys are On and which lists are monitored, keyed
by Favorites List file name (f_000001.hpd). Profiles belong to one configuration. To use them in another
one, the lists are matched by NAME first, because file numbers can differ between configurations; a list
whose name isn't found falls back to the same file name, when that list isn't already taken by a name
match. Lists that can't be matched are left out of the imported profile and reported; applying the
profile then leaves those lists as they are (keys_model.apply_profile).

Sources: another saved configuration, a profiles file (written by Export, or a scan-profiles/*.json
copied from another PC), and the scanner's current keys (a snapshot of f_list.cfg and profile.cfg).
"""
import json
from pathlib import Path

FORMAT = 'sds-manager-scan-profiles'
MAX_BYTES = 5 * 1024 * 1024


def _bools(value, length=100):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError('a key list must have %d On/Off values' % length)
    return [bool(v) for v in value]


def clean_profile(profile):
    """A checked copy of one profile; ValueError when it isn't one."""
    if not isinstance(profile, dict):
        raise ValueError('not a scan profile')
    out = {'fl': _bools(profile.get('fl')), 'monitor': {}, 'sys': {}, 'dept': {}}
    for part in ('monitor', 'sys', 'dept'):
        value = profile.get(part, {})
        if not isinstance(value, dict):
            raise ValueError('scan profile part %r is not a table' % part)
        for key, states in value.items():
            if not isinstance(key, str):
                raise ValueError('scan profile part %r has a bad name' % part)
            out[part][key] = bool(states) if part == 'monitor' else _bools(states)
    return out


def list_names(folder):
    """{filename: list name} of a configuration folder or scanner card root."""
    import flist_settings
    root = Path(folder)
    if root.name.lower() != 'bcdx36hp':
        root = root / 'BCDx36HP'
    raw = (root / 'favorites_lists' / 'f_list.cfg').read_bytes()
    return {l['filename']: l['name'] for l in flist_settings.read_lists(raw)}


def match_lists(source_names, target_names):
    """{source filename (lower case): target filename as the target writes it} — by list name first,
    then by file name. Both arguments are {filename: name}; file names are compared without case."""
    source = {f.lower(): (n or '').strip().casefold() for f, n in source_names.items()}
    target = {f.lower(): f for f in target_names}
    target_by_name = {}
    for f, n in target_names.items():
        target_by_name.setdefault((n or '').strip().casefold(), []).append(f.lower())
    source_count = {}
    for n in source.values():
        source_count[n] = source_count.get(n, 0) + 1
    mapping, taken = {}, set()
    for filename, name in source.items():          # a name found once on each side
        candidates = target_by_name.get(name, [])
        if name and len(candidates) == 1 and source_count[name] == 1:
            mapping[filename] = target[candidates[0]]
            taken.add(candidates[0])
    for filename in source:                         # the rest by file name
        if filename not in mapping and filename in target and filename not in taken:
            mapping[filename] = target[filename]
            taken.add(filename)
    return mapping


def remap(profile, mapping):
    """(profile for the target configuration, [source filenames left out])."""
    profile = clean_profile(profile)
    out = {'fl': profile['fl'], 'monitor': {}, 'sys': {}, 'dept': {}}
    dropped = set()
    for part in ('monitor', 'sys'):
        for filename, value in profile[part].items():
            target = mapping.get(filename.lower())
            if target is None:
                dropped.add(filename.lower())
            else:
                out[part][target] = value
    for key, value in profile['dept'].items():
        filename, _, system = key.partition('|')
        target = mapping.get(filename.lower())
        if target is None:
            dropped.add(filename.lower())
        else:
            out['dept'][target + '|' + system] = value
    return out, sorted(dropped)


# ---------------------------------------------------------------- sources
def from_configuration(folder):
    """(profiles, {filename: list name}) saved for another configuration."""
    import keys_model as km
    profiles = {}
    for name, profile in km.load_profiles(folder).items():
        try:
            profiles[str(name)] = clean_profile(profile)
        except ValueError:
            continue
    return profiles, list_names(folder)


def from_scanner(card, name):
    """({name: the scanner's current keys and monitor states}, {filename: list name})."""
    import keys_model as km
    root = Path(card)
    if root.name.lower() == 'bcdx36hp':
        root = root.parent
    return {name: clean_profile(km.model_for_configuration(root).profile())}, list_names(root)


def read_file(path):
    """(profiles, {filename: list name} or {} when the file has no list names)."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('The file is larger than 5 MB; it is not a scan profiles file.')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError):
        raise ValueError('The file is not a scan profiles file (it is not JSON).')
    if isinstance(data, dict) and data.get('format') == FORMAT:
        raw, names = data.get('profiles'), data.get('lists') or {}
        if not isinstance(names, dict):
            names = {}
        names = {str(f): str(n) for f, n in names.items()}
    else:                                           # a scan-profiles/<configuration>.json copied as it is
        raw, names = data, {}
    if not isinstance(raw, dict) or not raw:
        raise ValueError('The file has no scan profiles.')
    profiles, bad = {}, []
    for name, profile in raw.items():
        try:
            profiles[str(name)] = clean_profile(profile)
        except ValueError:
            bad.append(str(name))
    if not profiles:
        raise ValueError('None of the scan profiles in the file could be read.')
    return profiles, names


def write_file(path, profiles, names, configuration=''):
    """Write the chosen profiles with their list names, so another configuration can match them."""
    data = {'format': FORMAT, 'version': 1, 'configuration': configuration,
            'lists': dict(names),
            'profiles': {name: clean_profile(p) for name, p in profiles.items()}}
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- merging
def unique_name(name, existing):
    if name not in existing:
        return name
    n = 2
    while f'{name} ({n})' in existing:
        n += 1
    return f'{name} ({n})'


def merge(existing, incoming, source_names, target_names, replace=False):
    """Add incoming profiles to existing ones (a new dict).

    source_names may be {} (a profiles file without list names): then lists match by file name only.
    Returns (profiles, report) where report is [{'name', 'saved_as', 'left_out': [list names]}]. Without
    replace, a name already used gets " (2)" and so on; with replace, it is overwritten."""
    if source_names:
        mapping = match_lists(source_names, target_names)
        shown = {f.lower(): n for f, n in source_names.items()}
    else:
        mapping = {f.lower(): f for f in target_names}
        shown = {}
    result = dict(existing)
    report = []
    for name, profile in incoming.items():
        converted, dropped = remap(profile, mapping)
        saved_as = name if replace else unique_name(name, result)
        result[saved_as] = converted
        report.append({'name': name, 'saved_as': saved_as, 'left_out': [shown.get(f, f) for f in dropped]})
    return result, report
