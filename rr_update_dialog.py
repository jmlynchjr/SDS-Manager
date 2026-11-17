# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""Favorites → Update Favorites List from RadioReference… (v0.1.35), and in the personal build
Favorites → Update Favorites List from Uniden Database… (v0.1.37, the same window reading the local database).

The window lists the systems of the chosen Favorites List with the RadioReference system each one is linked
to (rr_links), lets you choose or change that system, then reads them from RadioReference (live, through your
own account, nothing kept) and shows what differs (rr_update) with tick boxes. Apply makes the ticked changes in
the open configuration as one Undo step; Save Configuration and Export to Scanner as usual.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QAbstractItemView, QHeaderView)

import favorites_clipboard as fc
import rr_links
import rr_update

YES, NO = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
CHANGE_ROLE = Qt.ItemDataRole.UserRole


def plain_name(text):
    """For matching names: case, spacing and RadioReference's '(conventional)' label don't count."""
    return ' '.join(str(text).removesuffix(' (conventional)').split()).casefold()


def _rr_kind(records):
    """'Trunk' or 'Conventional': the kinds of RadioReference entries that fit this system."""
    return 'Trunk' if fc.kind_of(records[0]) == 'Trunk' else 'Conventional'


class ChooseRRSystemDialog(QDialog):
    """State, county and system on RadioReference, for one system of a list. The system with the same name is
    chosen when there is one."""

    def __init__(self, workspace, records, link=None, parent=None):
        super().__init__(parent)
        self.workspace, self.records, self.link = workspace, records, link
        self.kind = _rr_kind(records)
        self.name = fc.system_name(records)
        self.setWindowTitle('RadioReference system for ' + self.name)
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        # v0.1.36: never smaller than what the contents need. With the theme's padding, a fixed small size
        # squeezed the dropdowns until their text was cut off.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setSpacing(10)
        intro = QLabel(f'Choose the RadioReference system that <b>{self.name}</b> ({self.kind.lower()}) comes from. '
                       'Trunked systems are listed under the state (Statewide) and under the counties they cover.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(8)
        self.state = QComboBox()
        self.county = QComboBox()
        self.system = QComboBox()
        for combo in (self.state, self.county, self.system):
            combo.setMinimumContentsLength(32)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumHeight(max(32, int(combo.sizeHint().height())))
        form.addRow('State', self.state)
        form.addRow('County', self.county)
        form.addRow('System', self.system)
        layout.addLayout(form)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(buttons)
        self.state.currentIndexChanged.connect(self.state_changed)
        self.county.currentIndexChanged.connect(self.county_changed)
        self.system.currentIndexChanged.connect(self.system_changed)
        self.want_state, self.want_county = self._starting_place()
        self.adjustSize()
        self.load_states()

    def _starting_place(self):
        if self.link and self.link.get('state'):
            return self.link.get('state'), self.link.get('county')
        ws = self.workspace
        try:
            region = ws.region_choice.currentData()
            if isinstance(region, tuple) and region and region[0] == 'rr-state':
                return region[1], ws.county_choice.currentData()
        except (AttributeError, TypeError):
            pass
        return None, None

    def say(self, text):
        self.status.setText(text)

    def load_states(self):
        self.state.blockSignals(True)
        self.state.clear()
        self.state.addItem('Loading states from RadioReference…', None)
        self.state.blockSignals(False)

        def done(states, error):
            self.state.blockSignals(True)
            self.state.clear()
            self.state.addItem('Choose a state…', None)
            for stid, name in states or []:
                self.state.addItem(name, stid)
            self.state.blockSignals(False)
            if error:
                self.say(f'RadioReference: {error}')
            if self.want_state is not None:
                index = self.state.findData(self.want_state)
                if index >= 0:
                    self.state.setCurrentIndex(index)
        self.workspace._rr_run('update-states', lambda b: b.states(1) + b.states(2), done)

    def state_changed(self, _index=None):
        stid = self.state.currentData()
        self.county.blockSignals(True)
        self.county.clear()
        self.county.addItem('Statewide systems and agencies', None)
        self.county.blockSignals(False)
        self.system.clear()
        if stid is None:
            return

        def done(counties, error):
            if self.state.currentData() != stid:
                return
            self.county.blockSignals(True)
            for ctid, name in counties or []:
                self.county.addItem(f'{name} County', ctid)
            self.county.blockSignals(False)
            want = self.want_county
            self.want_county = None
            index = self.county.findData(want) if want is not None else -1
            if index > 0:
                self.county.setCurrentIndex(index)
            else:
                self.county_changed()
        self.workspace._rr_run('update-counties', lambda b: b.counties(stid), done)

    def county_changed(self, _index=None):
        stid, ctid = self.state.currentData(), self.county.currentData()
        self.system.blockSignals(True)
        self.system.clear()
        self.system.addItem('Loading systems…', None)
        self.system.blockSignals(False)
        if stid is None:
            return

        def done(entries, error):
            if self.state.currentData() != stid or self.county.currentData() != ctid:
                return
            self.system.blockSignals(True)
            self.system.clear()
            self.system.addItem('Choose a system…', None)
            fitting = sorted((e for e in entries or [] if e[1] == self.kind), key=lambda e: e[0].casefold())
            for label, _kind, key in fitting:
                self.system.addItem(label, (key[0], int(key[1]), label.removesuffix(' (conventional)')))
            self.system.blockSignals(False)
            wanted = self.link['key'] if self.link else None
            pick = next((i for i in range(1, self.system.count())
                         if wanted and tuple(self.system.itemData(i)[:2]) == tuple(wanted)), None)
            if pick is None:
                pick = next((i for i in range(1, self.system.count())
                         if plain_name(self.system.itemText(i)) == plain_name(self.name)), None)
            if pick is not None:
                self.system.setCurrentIndex(pick)
            where = 'in this county' if ctid else 'statewide'
            self.say(f'{len(fitting)} {self.kind.lower()} systems {where}.' +
                     ('' if pick is not None else ' None has the same name; choose one, or try another county.'))
            self.system_changed()
        self.workspace._rr_run('update-systems', lambda b: b.systems(stid, ctid), done)

    def system_changed(self, _index=None):
        self.ok.setEnabled(bool(self.system.currentData()))

    def chosen(self):
        data = self.system.currentData()
        if not data:
            return None
        return {'key': (data[0], data[1]), 'label': data[2], 'state': self.state.currentData(),
                'county': self.county.currentData()}


class RRUpdateDialog(QDialog):
    """One Favorites List (v0.1.35), or every list of the configuration (Check All Lists, v0.1.38). Systems are
    keyed (list name, entry index) throughout."""

    def __init__(self, window, draft_name, only_entry=None, parent=None, source='rr', drafts=None):
        super().__init__(parent or window)
        self.source = source             # 'rr', or in the personal build 'uniden' (v0.1.37)
        self.where = self.short = 'RadioReference'
        self.folder = None
        self.window_ = window
        self.workspace = window.workspace
        self.drafts = drafts or {draft_name: self.workspace.drafts[draft_name]}   # list name -> entries
        self.all_lists = drafts is not None
        self.draft_name = draft_name or 'all Favorites Lists'
        self.configuration = Path(getattr(window, 'active_scanner_configuration', '') or '').name
        self.results = {}                # (list, entry index) -> (changes, label)
        self.items = []
        self.applied = False
        title = 'Check All Lists' if self.all_lists else 'Update'
        self.setWindowTitle(f'{title} from {self.short} — ' + (self.configuration if self.all_lists else draft_name))
        self.resize(1000, 760)
        layout = QVBoxLayout(self)
        what = 'every Favorites List of this configuration' if self.all_lists else 'this Favorites List'
        intro = QLabel(f'Compare the systems of {what} with {self.where} as it is now, then choose '
                       'which changes to make. Only what you tick changes; your quick keys, number tags, avoids, '
                       'alerts and other settings stay as they are. Changes go into the open configuration, as one '
                       'Undo step; Save Configuration and Export to Scanner as usual.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.systems = QTableWidget(0, 3)
        self.systems.setHorizontalHeaderLabels(['System in the list', f'{self.short} system', ''])
        self.systems.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.systems.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.systems.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.systems.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.systems.verticalHeader().setVisible(False)
        self.systems.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.systems)
        row = QHBoxLayout()
        self.check = QPushButton('CHECK FOR CHANGES')
        self.check.setToolTip(f'Read the ticked systems from {self.where} and list what differs')
        self.check.clicked.connect(self.check_changes)
        row.addWidget(self.check)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Change'])
        self.tree.itemChanged.connect(self.item_changed)
        layout.addWidget(self.tree, 1)
        picks = QHBoxLayout()
        for text, how in (('TICK SUGGESTED', 'default'), ('TICK ALL', 'all'), ('UNTICK ALL', 'none')):
            button = QPushButton(text)
            button.clicked.connect(lambda _c=False, h=how: self.tick(h))
            picks.addWidget(button)
        picks.addStretch(1)
        self.apply_button = QPushButton('APPLY TICKED CHANGES')
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        picks.addWidget(self.apply_button)
        close = QPushButton('CLOSE')
        close.clicked.connect(self.accept)
        picks.addWidget(close)
        layout.addLayout(picks)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.only_entry = only_entry
        self.fill_systems()

    # ---- systems and their links ----------------------------------------------------------------------
    def entries_of(self, key):
        return self.drafts[key[0]]

    def records_of(self, key):
        return self.drafts[key[0]][key[1]]['records']

    def list_file(self, draft):
        entries = self.drafts[draft]
        return Path(entries[0].get('source_path') or '').name if entries else ''

    def system_entries(self):
        """[(list name, entry index)] of every system shown."""
        found = []
        for draft, entries in self.drafts.items():
            for i, e in enumerate(entries):
                if e.get('scope') != 'metadata' and e.get('records'):
                    found.append((draft, i))
        return found

    def link_for(self, key):
        records = self.records_of(key)
        return rr_links.get(self.configuration, self.list_file(key[0]), records)

    def fill_systems(self):
        rows = self.system_entries()
        self.systems.setRowCount(len(rows))
        self.row_entry = []
        for r, key in enumerate(rows):
            records = self.records_of(key)
            label = f'{fc.system_name(records)}  ({_rr_kind(records).lower()})'
            if self.all_lists:
                label = f'{key[0]} — {label}'
            name = QTableWidgetItem(label)
            name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            link = self.link_for(key)
            wanted = (self.only_entry is None or self.only_entry == key[1]) and link is not None
            name.setCheckState(Qt.CheckState.Checked if wanted else Qt.CheckState.Unchecked)
            self.systems.setItem(r, 0, name)
            self.systems.setItem(r, 1, QTableWidgetItem(link['label'] or f'{link["key"][0]} {link["key"][1]}'
                                                        if link else 'Not linked yet: choose it'))
            choose = QPushButton('CHOOSE…' if link is None else 'CHANGE…')
            choose.clicked.connect(lambda _c=False, row=r: self.choose(row))
            self.systems.setCellWidget(r, 2, choose)
            # v0.1.36: rows tall enough for the button, which the theme pads (it was cut off before).
            self.systems.setRowHeight(r, max(34, int(choose.sizeHint().height()) + 6))
            self.row_entry.append(key)
        shown = min(max(len(rows), 1), 8 if self.all_lists else 5)    # then it scrolls
        height = int(self.systems.horizontalHeader().sizeHint().height()) + 6
        height += sum(int(self.systems.rowHeight(r)) for r in range(shown)) if rows else 34
        self.systems.setFixedHeight(max(80, height))
        if not rows:
            self.say('There are no systems to check.')
        elif self.all_lists:
            linked = sum(1 for key in rows if self.link_for(key) is not None)
            self.say(f'{linked} of {len(rows)} systems are linked to {self.where} and ticked. '
                     'CHOOSE… links the others.')

    def choose(self, row):
        key = self.row_entry[row]
        records = self.records_of(key)
        dialog = ChooseRRSystemDialog(self.workspace, records, self.link_for(key), self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.chosen():
            return
        c = dialog.chosen()
        rr_links.remember(self.configuration, self.list_file(key[0]), records, c['key'], c['label'], c['state'],
                          c['county'])
        self.relink(row)
        self.say(f'{fc.system_name(records)} is linked to {c["label"]} on RadioReference. CHECK FOR CHANGES compares them.')

    def relink(self, row):
        """Fill the table again, keeping the other ticks, and tick the system just linked."""
        ticked = set(self.chosen_entries())
        ticked.add(self.row_entry[row])
        self.fill_systems()
        for r, key in enumerate(self.row_entry):
            item = self.systems.item(r, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if key in ticked else Qt.CheckState.Unchecked)

    def chosen_entries(self):
        out = []
        for r, key in enumerate(self.row_entry):
            item = self.systems.item(r, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(key)
        return out

    # ---- comparing ------------------------------------------------------------------------------------
    def check_changes(self):
        picked = self.chosen_entries()
        if not picked:
            self.say(f'Tick at least one system (CHOOSE… links a system to the {self.short} first).')
            return
        jobs = []
        for key in picked:
            link = self.link_for(key)
            if link is None:
                self.say(f'{fc.system_name(self.records_of(key))} isn\'t linked to a {self.short} system yet: '
                         'use CHOOSE….')
                return
            jobs.append((key, link))
        self.check.setEnabled(False)
        self.say(f'Reading {len(jobs)} system(s) from {self.where}…')

        def work(browser):
            loaded, cache = {}, {}
            for key, link in jobs:                   # a system in several lists is read once
                wanted = tuple(link['key'])
                if wanted not in cache:
                    cache[wanted] = browser.load(link['key'])
                section, why = cache[wanted]
                loaded[key] = (link, section, why)
            return loaded

        self.workspace._rr_run('update-load', work, self.loaded)

    def loaded(self, result, error):
        self.check.setEnabled(True)
        if error or result is None:
            self.say(f'RadioReference: {error or "not signed in (Tools → RadioReference Account…)"}')
            return
        self.results = {}
        problems = []
        for key, (link, section, why) in result.items():
            records = self.records_of(key)
            name = fc.system_name(records)
            if self.all_lists:
                name = f'{key[0]} — {name}'
            if section is None:
                problems.append(f'{name}: {why}')
                continue
            try:
                rr_records = fc.database_clip(section['records'])['records']
                changes = rr_update.compare(records, rr_records)
            except (ValueError, fc.ClipboardError) as exc:
                problems.append(f'{name}: {exc}')
                continue
            self.results[key] = (changes, link['label'] or section.get('name', ''))
        self.show_changes()
        total = sum(len(c) for c, _l in self.results.values())
        lists = len({key[0] for key, (c, _l) in self.results.items() if c})
        text = (f'{total} difference(s) found' + (f' in {lists} list(s)' if self.all_lists else '') +
                '. Suggested changes are ticked; untick anything you want to keep as it is.'
                if total else f'No differences: the ticked systems match {self.where}.')
        if problems:
            text += '\n' + '\n'.join(problems)
        self.say(text)

    def show_changes(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        self.items = []                  # (tree item, (list, entry index), change) for every change shown
        parents = {}
        for key, (changes, label) in self.results.items():
            name = fc.system_name(self.records_of(key))
            holder = None
            if self.all_lists:
                holder = parents.get(key[0])
                if holder is None:
                    holder = parents[key[0]] = QTreeWidgetItem([key[0]])
                    self.tree.addTopLevelItem(holder)
                    holder.setExpanded(True)
            top = QTreeWidgetItem([f'{name} — {self.short}: {label}' + ('' if changes else ' (no differences)')])
            if holder is None:
                self.tree.addTopLevelItem(top)
            else:
                holder.addChild(top)
            for group, title, count in rr_update.summary(changes):
                head = QTreeWidgetItem([f'{title} ({count})'])
                head.setFlags(head.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                head.setCheckState(0, Qt.CheckState.Unchecked)      # the group's box ticks or unticks them all
                top.addChild(head)
                for change in changes:
                    if change['group'] != group:
                        continue
                    item = QTreeWidgetItem([change['text']])
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    head.addChild(item)               # first, so the group's box follows its items
                    item.setCheckState(0, Qt.CheckState.Checked if change['default'] else Qt.CheckState.Unchecked)
                    item.setData(0, CHANGE_ROLE, (key[0], key[1], change['id']))
                    self.items.append((item, key, change))
                head.setExpanded(count <= 40)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        self.update_apply()

    def tick(self, how):
        self.tree.blockSignals(True)
        for item, _key, change in self.items:
            on = how == 'all' or (how == 'default' and change['default'])
            item.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self.update_apply()

    def item_changed(self, _item, _column):
        self.update_apply()

    def ticked(self):
        chosen = {}
        for item, key, change in self.items:
            if item.checkState(0) == Qt.CheckState.Checked:
                chosen.setdefault(key, []).append(change)
        return chosen

    def update_apply(self):
        count = sum(len(v) for v in self.ticked().values())
        self.apply_button.setEnabled(count > 0)
        self.apply_button.setText(f'APPLY {count} TICKED CHANGE{"S" if count != 1 else ""}' if count
                                  else 'APPLY TICKED CHANGES')

    # ---- applying ---------------------------------------------------------------------------------------
    def apply_changes(self):
        chosen = self.ticked()
        if not chosen:
            return
        count = sum(len(v) for v in chosen.values())
        lists = sorted({key[0] for key in chosen})
        where = lists[0] if len(lists) == 1 else f'{len(lists)} Favorites Lists'
        if QMessageBox.question(self, f'Update from {self.short}',
                                f'Make {count} change(s) in {where}?\n\nThis changes the open configuration '
                                'only (one Undo step). The scanner isn\'t touched until you Export to Scanner.',
                                YES | NO, YES) != YES:
            return
        self.workspace._snapshot()
        kept, done, clashes = [], 0, []
        for key in sorted(chosen):
            report = rr_update.apply(self.entries_of(key), key[1], chosen[key])
            done += report['done']
            kept += report['kept']
            clashes += report.get('clashes', [])
        self.workspace.refresh_draft()
        self.applied = True
        text = f'{done} change(s) made in {where}.'
        if kept:
            text += '\n\nLeft as they are:\n' + '\n'.join(f'  • {t} — {why}' for t, why in kept[:12])
        if clashes:
            text += (f'\n\n{len(clashes)} quick key(s) or number tag(s) of new items were already used; they went to '
                     'the next free numbers.')
        self.results = {}
        self.items = []
        self.tree.clear()
        self.update_apply()
        self.say(text.split('\n')[0] + ' CHECK FOR CHANGES again to see what is left.')
        save = getattr(self.window_, 'save_draft_to_configuration', None)
        if QMessageBox.question(self, f'Update from {self.short}', text + '\n\nSave the configuration now?',
                                YES | NO, YES) == YES and save is not None:
            save()

    def say(self, text):
        self.status.setText(text)


class RRUpdateMixin:
    """Favorites → Update Favorites List from RadioReference… and Check All Lists… on the main window."""

    def _update_ready(self, title, source):
        if self._config_folder(title) is None:
            return False
        if source == 'rr' and self.workspace._rr_client_browser() is None:
            QMessageBox.information(self, title, 'Sign in to RadioReference first: Tools → RadioReference Account….')
            return False
        return True

    def update_list_from_rr(self, only_entry=None, parent=None, draft=None, source='rr'):
        title = 'Update from RadioReference' if source == 'rr' else 'Update from Uniden Database'
        if self._config_folder(title) is None:
            return False
        draft = draft or self.workspace.current_draft
        if not draft or not fc.is_native(self.workspace.drafts.get(draft)):
            QMessageBox.information(self, title, 'Choose a Favorites List of the open configuration first.')
            return False
        if not self._update_ready(title, source):
            return False
        dialog = RRUpdateDialog(self, draft, only_entry, parent, source)
        dialog.exec()
        if dialog.applied:
            self._refresh_configuration_label()
        return dialog.applied

    def check_all_lists(self, source='rr'):
        """Favorites → Check All Lists… (v0.1.38): every linked system of every list of the open configuration,
        in one window."""
        title = 'Check All Lists'
        if not self._update_ready(title, source):
            return False
        lists = {name: entries for name, entries in self._list_drafts().items() if fc.is_native(entries)}
        if not lists:
            QMessageBox.information(self, title, 'The open configuration has no Favorites Lists.')
            return False
        dialog = RRUpdateDialog(self, None, None, None, source, lists)
        dialog.exec()
        if dialog.applied:
            self._refresh_configuration_label()
        return dialog.applied
