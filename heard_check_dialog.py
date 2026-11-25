# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Tools → Check Heard Talkgroups with RadioReference… (v0.1.39): the window. The work is in heard_check."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLayout,
                             QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

import favorites_clipboard as fc
import heard_check
import monitor_link
import rr_links
from rr_update_dialog import ChooseRRSystemDialog

YES = QMessageBox.StandardButton.Yes
STATUS_TEXT = {'missing': 'Not in your lists', 'unnamed': 'In your lists, no name',
               'no_system': 'System not in your lists'}


class HeardCheckDialog(QDialog):
    COLUMNS = ['Use', 'System', 'TGID', 'Calls', 'Last heard', 'Now', 'Name to use', 'Department (new ones)',
               'Service type', 'RadioReference']

    def __init__(self, window, drafts, days=heard_check.DAYS, heard=None):
        super().__init__(window)
        self.window_ = window
        self.workspace = window.workspace
        self.drafts = drafts                     # list name -> entries (the open configuration's lists)
        self.configuration = Path(getattr(window, 'active_scanner_configuration', '') or '').name
        self.rr = {}                             # system folded -> {tgid: info} once looked up
        self.applied = False
        self.setWindowTitle('Check Heard Talkgroups with RadioReference')
        self.resize(1250, 760)
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        intro = QLabel('Talkgroups SDS100 Monitor heard that aren\'t in this configuration\'s Favorites Lists, or are '
                       'in them with no real name. LOOK UP ON RADIOREFERENCE reads each system\'s talkgroups (through '
                       'the RadioReference system it is linked to, as for Update from RadioReference) and suggests '
                       'names, departments and service types. Tick what to use and press Apply: missing talkgroups '
                       'are added, unnamed ones are named, as one Undo step. Save Configuration and Export as usual.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        top = QHBoxLayout()
        top.addWidget(QLabel('Heard in the last'))
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(days)
        self.days.setSuffix(' days')
        top.addWidget(self.days)
        reload_button = QPushButton('RELOAD')
        reload_button.setToolTip('Read the Monitor\'s history again')
        reload_button.clicked.connect(self.reload)
        top.addWidget(reload_button)
        top.addStretch(1)
        self.lookup_button = QPushButton('LOOK UP ON RADIOREFERENCE')
        self.lookup_button.clicked.connect(self.look_up)
        top.addWidget(self.lookup_button)
        layout.addLayout(top)
        self.systems = QTableWidget(0, 3)
        self.systems.setHorizontalHeaderLabels(['System heard', 'RadioReference system', ''])
        self.systems.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.systems.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.systems.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.systems.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.systems.verticalHeader().setVisible(False)
        layout.addWidget(self.systems)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        picks = QHBoxLayout()
        for text, how in (('TICK SUGGESTED', 'suggested'), ('UNTICK ALL', 'none')):
            button = QPushButton(text)
            button.clicked.connect(lambda _c=False, h=how: self.tick(h))
            picks.addWidget(button)
        picks.addStretch(1)
        self.apply_button = QPushButton('APPLY TICKED')
        self.apply_button.clicked.connect(self.apply_ticked)
        picks.addWidget(self.apply_button)
        close = QPushButton('CLOSE')
        close.clicked.connect(self.accept)
        picks.addWidget(close)
        layout.addLayout(picks)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.reload(heard)

    # ---- reading -----------------------------------------------------------------------------------
    def reload(self, heard=None):
        """RELOAD (or a first opening): read the Monitor's history; otherwise use what was read."""
        if heard is None or isinstance(heard, bool):
            heard = heard_check.heard_talkgroups(int(self.days.value()))
        self.heard = heard
        self.items = heard_check.unknown_talkgroups(heard, self.drafts)
        self.rows = []
        for item in self.items:
            info = self.info_for(item)
            name, department, tick = heard_check.suggested(item, info)
            self.rows.append({'item': item, 'name': name, 'department': department,
                              'service': (info or {}).get('service', heard_check.rr_convert.OTHER),
                              'tick': tick})
        self.fill_systems()
        self.fill_table()
        if not heard:
            self.say('SDS100 Monitor has no reception history in these days (it is read from '
                     f'{monitor_link.monitor_data_dir() / "history"}).')
        elif not self.items:
            self.say('Every talkgroup the Monitor heard in these days is in your lists with a name.')
        else:
            counts = {k: sum(1 for i in self.items if i['status'] == k) for k in STATUS_TEXT}
            self.say(f'{counts["missing"]} heard talkgroup(s) aren\'t in your lists and {counts["unnamed"]} have no '
                     'name' + (f'; {counts["no_system"]} are on systems that aren\'t in your lists' if counts['no_system']
                               else '') + '. LOOK UP ON RADIOREFERENCE for names.')

    def info_for(self, item):
        return self.rr.get(heard_check._fold(item['system']), {}).get(item['tgid'])

    # ---- systems and their RadioReference links -----------------------------------------------------
    def system_keys(self):
        """[(system folded, label, (draft, entry index) or None)] for the systems with something to check."""
        seen, out = set(), []
        for item in self.items:
            key = heard_check._fold(item['system'])
            if key in seen:
                continue
            seen.add(key)
            out.append((key, item['system'], item['systems'][0] if item['systems'] else None))
        return out

    def list_file(self, draft):
        entries = self.drafts.get(draft) or []
        return Path(entries[0].get('source_path') or '').name if entries else ''

    def link_for(self, where):
        """The RadioReference link of the first list system of that name that has one."""
        if where is None:
            return None
        key = heard_check._fold(fc.system_name(self.drafts[where[0]][where[1]]['records']))
        for draft, entries in self.drafts.items():
            for entry in entries or []:
                records = entry.get('records') or []
                if entry.get('scope') == 'metadata' or not records or heard_check._fold(fc.system_name(records)) != key:
                    continue
                link = rr_links.get(self.configuration, self.list_file(draft), records)
                if link and link['key'][0] == 'trs':
                    return link
        return None

    def fill_systems(self):
        keys = self.system_keys()
        self.system_rows = keys
        self.systems.setRowCount(len(keys))
        for r, (_key, label, where) in enumerate(keys):
            self.systems.setItem(r, 0, QTableWidgetItem(label))
            link = self.link_for(where)
            text = (link['label'] or f'trs {link["key"][1]}') if link else (
                'Not linked yet: choose it' if where else 'Not in your lists: add the system first')
            self.systems.setItem(r, 1, QTableWidgetItem(text))
            if where is not None:
                button = QPushButton('CHANGE…' if link else 'CHOOSE…')
                button.clicked.connect(lambda _c=False, row=r: self.choose(row))
                self.systems.setCellWidget(r, 2, button)
                self.systems.setRowHeight(r, max(34, int(button.sizeHint().height()) + 6))
        shown = min(max(len(keys), 1), 5)
        height = int(self.systems.horizontalHeader().sizeHint().height()) + 6
        height += sum(int(self.systems.rowHeight(r)) for r in range(shown)) if keys else 34
        self.systems.setFixedHeight(max(80, height))

    def choose(self, row):
        _key, _label, where = self.system_rows[row]
        records = self.drafts[where[0]][where[1]]['records']
        dialog = ChooseRRSystemDialog(self.workspace, records, self.link_for(where), self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.chosen():
            return
        c = dialog.chosen()
        rr_links.remember(self.configuration, self.list_file(where[0]), records, c['key'], c['label'],
                          c['state'], c['county'])
        self.fill_systems()
        self.say(f'{fc.system_name(records)} is linked to {c["label"]}. LOOK UP ON RADIOREFERENCE reads its talkgroups.')

    # ---- RadioReference ------------------------------------------------------------------------------
    def look_up(self):
        jobs, unlinked = {}, []
        for key, label, where in self.system_keys():
            link = self.link_for(where)
            if link is None:
                if where is not None:
                    unlinked.append(label)
                continue
            jobs[key] = link['key'][1]
        if not jobs:
            self.say('No system is linked to RadioReference yet: use CHOOSE… beside each system.' if unlinked else
                     'Nothing to look up.')
            return
        self.lookup_button.setEnabled(False)
        self.say(f'Reading {len(jobs)} system(s) from RadioReference…')

        def work(browser):
            return {key: heard_check.fetch_rr(browser, sid) for key, sid in jobs.items()}

        self.unlinked = unlinked
        self.workspace._rr_run('heard-check', work, self.looked_up)

    def looked_up(self, result, error):
        self.lookup_button.setEnabled(True)
        if error or result is None:
            self.say(f'RadioReference: {error or "not signed in (Tools → RadioReference Account…)"}')
            return
        self.rr.update(result)
        found = 0
        for row in self.rows:
            info = self.info_for(row['item'])
            if info:
                found += 1
                row['name'], row['department'], row['tick'] = heard_check.suggested(row['item'], info)
                row['service'] = info['service']
        self.fill_table()
        missing = sum(1 for row in self.rows if row['item']['status'] != 'no_system' and not self.info_for(row['item'])
                      and heard_check._fold(row['item']['system']) in self.rr)
        text = f'RadioReference has {found} of the {len(self.rows)} talkgroup(s). Suggested ones are ticked; you can ' \
               'change a name or department before applying.'
        if missing:
            text += f' {missing} aren\'t on RadioReference (yet): name them yourself, or leave them.'
        if getattr(self, 'unlinked', None):
            text += ' Not linked, so not looked up: ' + ', '.join(self.unlinked) + ' (CHOOSE…).'
        self.say(text)

    # ---- the table -----------------------------------------------------------------------------------
    def fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.rows))
        self.dept_boxes = []
        for r, row in enumerate(self.rows):
            item, info = row['item'], self.info_for(row['item'])
            use = QTableWidgetItem('')
            can_use = item['status'] != 'no_system'
            use.setFlags((Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable) if can_use
                         else Qt.ItemFlag.ItemIsEnabled)
            use.setCheckState(Qt.CheckState.Checked if row['tick'] and can_use else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, use)
            now = STATUS_TEXT[item['status']]
            if item['status'] == 'unnamed':
                now += ' (' + ', '.join(sorted({monitor_link.list_label(loc['draft']) for loc in item['locations']})) + ')'
            values = [item['system'], item['tgid'], str(item['calls']), item['last'][:16], now]
            for c, value in enumerate(values, start=1):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, cell)
            name = QTableWidgetItem(row['name'])
            name.setToolTip('The name the talkgroup gets. RadioReference\'s first, else what the scanner showed.')
            self.table.setItem(r, 6, name)
            if item['status'] == 'missing':
                box = QComboBox()
                box.setEditable(True)
                records = self.drafts[item['systems'][0][0]][item['systems'][0][1]]['records']
                choices = heard_check.departments(records)
                if row['department'] not in choices:
                    choices = [row['department']] + choices
                box.addItems(choices)
                box.setCurrentText(row['department'])
                box.setToolTip('An existing department, or a new one with this name')
                self.table.setCellWidget(r, 7, box)
                self.dept_boxes.append((r, box))
            else:
                cell = QTableWidgetItem('—' if item['status'] == 'unnamed' else '')
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, 7, cell)
            service = QTableWidgetItem(heard_check.service_label(row['service']) if item['status'] == 'missing' else '')
            service.setFlags(service.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 8, service)
            if info:
                note = ' • '.join(p for p in (info['category'], info['alpha'],
                                              'fully encrypted' if info['encrypted'] else '',
                                              'partly encrypted' if info['partly_encrypted'] else '') if p)
            elif heard_check._fold(item['system']) in self.rr:
                note = 'not on RadioReference'
            else:
                note = ''
            cell = QTableWidgetItem(note)
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 9, cell)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()

    def read_table(self):
        """Copy the ticks, names and departments from the table into self.rows."""
        boxes = dict(self.dept_boxes) if hasattr(self, 'dept_boxes') else {}
        for r, row in enumerate(self.rows):
            use, name = self.table.item(r, 0), self.table.item(r, 6)
            state = use.checkState() if use is not None else None
            if state in (Qt.CheckState.Checked, Qt.CheckState.Unchecked):
                row['tick'] = state == Qt.CheckState.Checked
            if name is not None and isinstance(name.text(), str):
                row['name'] = name.text()
            box = boxes.get(r)
            if box is not None and isinstance(box.currentText(), str):
                row['department'] = box.currentText()

    def tick(self, how):
        self.read_table()
        for row in self.rows:
            if how == 'none':
                row['tick'] = False
            else:
                row['tick'] = heard_check.suggested(row['item'], self.info_for(row['item']))[2]
        self.fill_table()

    # ---- applying ------------------------------------------------------------------------------------
    def choices(self):
        self.read_table()
        out = []
        for row in self.rows:
            if not row['tick'] or row['item']['status'] == 'no_system':
                continue
            name = ' '.join(row['name'].split())
            draft = (row['item']['locations'] or [{'draft': row['item']['systems'][0][0]}])[0]['draft']
            entries = self.drafts.get(draft) or []
            meta = entries[0] if entries and entries[0].get('scope') == 'metadata' else {}
            encoding = meta.get('encoding', 'cp1252')
            if not monitor_link.valid_name(name, encoding):
                raise ValueError(f'Talkgroup {row["item"]["tgid"]} ({row["item"]["system"]}): "{name}" is not a usable '
                                 'name (1–64 characters the list can store).')
            out.append((row['item'], name, row['department'].strip(), row['service']))
        return out

    def apply_ticked(self, _checked=False, confirm=True):
        try:
            choices = self.choices()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        if not choices:
            self.say('Tick the talkgroups to use first.')
            return False
        adds = sum(1 for c in choices if c[0]['status'] == 'missing')
        names = len(choices) - adds
        if confirm and QMessageBox.question(
                self, self.windowTitle(), f'Add {adds} talkgroup(s) and name {names}?') != YES:
            return False
        self.workspace._snapshot()
        try:
            named, added, made = heard_check.apply(self.drafts, choices)
        except ValueError as exc:
            self.workspace.undo_change()
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        self.workspace.refresh_draft()
        self.applied = True
        text = f'{added} talkgroup(s) added' + (f' ({made} new department(s))' if made else '') + \
               f' and {named} named. Save Scanner Configuration to keep them; Undo takes them back.'
        self.workspace.status.setText(text)
        self.reload(self.heard)                   # what's left; the history itself didn't change
        self.say(text)
        return True

    def say(self, text):
        self.status.setText(text)


class HeardCheckMixin:
    """Tools → Check Heard Talkgroups with RadioReference… on the main window."""

    def check_heard_talkgroups(self, days=heard_check.DAYS):
        title = 'Check Heard Talkgroups'
        if self._config_folder(title) is None:
            return False
        lists = {name: entries for name, entries in self._list_drafts().items() if fc.is_native(entries)}
        if not lists:
            QMessageBox.information(self, title, 'The open configuration has no Favorites Lists.')
            return False
        dialog = HeardCheckDialog(self, lists, days=days if isinstance(days, int) else heard_check.DAYS)
        dialog.exec()
        if dialog.applied:
            self._refresh_configuration_label()
        return dialog.applied
