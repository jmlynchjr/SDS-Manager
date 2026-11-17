# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""One data folder for everything SDS-Manager makes (v0.1.34).

    ~/.local/share/sds100-database-favorites-manager/
        database/downloads/   master database archives (downloaded, or a copy of the one you chose)
        database/versions/    rebuilt databases; database/current points at the one in use
        database/rebuilt/     Rebuild Full Database / Export One State File (Database → Advanced)
        firmware/             firmware files
        scanner-configurations/, scanner-backups/, emergency-restore-backups/, scan-profiles/
        exports/              .hpd lists, scan profiles, spreadsheets, key cards
        reports/              Compare with Scanner reports
        favorites/, history/, manifests/, export-state.json, monitor-keys.json

The folder keeps the name SDS100 Monitor already reads (monitor-keys.json, configurations). Before
0.1.34 the database and firmware lived in a second folder, ~/.local/share/SDS100DatabaseFavoritesManager;
migrate() moves its contents here once and leaves a link with the old name, so anything still using
that path finds the same files. Settings (~/.config) and the log (~/.local/state) stay where Linux
keeps them. Pure apart from show_saved(); never touches the scanner.
"""
import datetime
import os
import re
import shutil
from pathlib import Path

AREA = Path.home() / '.local' / 'share' / 'sds100-database-favorites-manager'
LEGACY = Path(os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local' / 'share')).expanduser() \
    / 'SDS100DatabaseFavoritesManager'
FOLDERS = {'downloads': 'database/downloads', 'versions': 'database/versions', 'rebuilt': 'database/rebuilt',
           'exports': 'exports', 'reports': 'reports', 'firmware': 'firmware', 'backups': 'scanner-backups'}


def folder(name, area=None):
    """A folder of the data area, created when missing."""
    path = Path(area or AREA) / FOLDERS.get(name, name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def stamp(now=None):
    return (now or datetime.datetime.now()).strftime('%Y-%m-%d %H%M%S')


def safe_name(text, fallback='SDS-Manager'):
    """A file name from free text: no slashes or control characters, not hidden, not too long."""
    text = re.sub(r'[\x00-\x1f/\\:*?"<>|]+', ' ', str(text)).strip().strip('.')
    return re.sub(r'\s+', ' ', text)[:90] or fallback


def unique(directory, filename):
    """directory/filename, or "name (2).ext" and so on when that already exists. Never overwrites."""
    directory = Path(directory)
    candidate = directory / filename
    if not candidate.exists() and not candidate.is_symlink():
        return candidate
    path = Path(filename)
    stem, suffix = (path.stem, path.suffix) if path.suffix and len(path.suffix) <= 6 else (filename, '')
    n = 2
    while True:
        candidate = directory / f'{stem} ({n}){suffix}'
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        n += 1


# ---------------------------------------------------------------- one-time move of the old folder
def _merge(source, target, moved, kept):
    if not target.exists() and not target.is_symlink():
        shutil.move(str(source), str(target))
        moved.append(target)
    elif (source.is_dir() and not source.is_symlink() and target.is_dir() and not target.is_symlink()):
        for child in sorted(source.iterdir()):
            _merge(child, target / child.name, moved, kept)
        try:
            source.rmdir()
        except OSError:
            pass
    else:
        kept.append(source)                         # both have it: leave the old one where it is


def migrate(area=None, legacy=None):
    """Move the old database folder into the data area once. Returns {'moved': n, 'kept': [paths],
    'linked': bool}. Safe to call every start: once the old name is a link it does nothing."""
    area, legacy = Path(area or AREA), Path(legacy or LEGACY)
    report = {'moved': 0, 'kept': [], 'linked': False}
    if legacy.is_symlink() or legacy.resolve() == area.resolve():
        return report
    area.mkdir(parents=True, exist_ok=True)
    if legacy.is_dir():
        moved, kept = [], []
        for child in sorted(legacy.iterdir()):
            _merge(child, area / child.name, moved, kept)
        report['moved'], report['kept'] = len(moved), [str(k) for k in kept]
        if kept:
            return report                           # something stayed behind: keep the real folder
        legacy.rmdir()
    elif legacy.exists():
        return report                               # a file with that name: leave it alone
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.symlink_to(area, target_is_directory=True)
    report['linked'] = True
    return report


# ---------------------------------------------------------------- telling the user
def show_saved(parent, title, path, text='Saved to the SDS-Manager data folder:'):
    """A message naming where a file went, with Open Folder."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import QMessageBox
    path = Path(path)
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(f'{text}\n\n{path}')
    show = box.addButton('Open Folder', QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()
    if box.clickedButton() is show:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path if path.is_dir() else path.parent)))
