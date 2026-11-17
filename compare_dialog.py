# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 J. Lynch. See LICENSE.
"""File → Compare Configuration with Scanner… (v0.1.32) and File → Compare Two Configurations… (v0.1.38).
Read only.

The comparison itself is config_compare (pure, tested); this is the window that shows it.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QLayout, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

import config_compare as cc

STATUS = {'same': 'Same', 'different': 'Different', 'configuration only': 'Only in the configuration',
          'scanner only': 'Only on the scanner', 'unreadable': 'Could not be read'}


def comparison_choices(configurations, backups, open_folder=None):
    """[(label, folder)] for the two lists: saved configurations (the open one first and marked), then scanner
    backups, newest first. configurations: [(folder, manifest)]; backups: [{'name', 'path'}] oldest first."""
    found = []
    for folder, manifest in configurations:
        name = str(manifest.get('name') or Path(folder).name)
        is_open = open_folder is not None and Path(folder).resolve() == Path(open_folder).resolve()
        found.append((not is_open, name.casefold(), name + (' (open)' if is_open else ''), str(folder)))
    found.sort()
    out = [(label, folder) for _o, _n, label, folder in found]
    for backup in reversed(backups):
        out.append(('Scanner backup ' + backup_label(backup['name']), str(backup['path'])))
    return out


def backup_label(stamp):
    """'20261114T204812Z' → '2026-11-14 20:48 UTC'."""
    text = str(stamp)
    if len(text) >= 15 and text[8] == 'T':
        return f'{text[0:4]}-{text[4:6]}-{text[6:8]} {text[9:11]}:{text[11:13]} UTC' + text[16:].replace('-', ' #')
    return text


def short_name(label):
    return label.removesuffix(' (open)')


class ChooseComparisonDialog(QDialog):
    """The two configurations (or scanner backups) to compare."""

    def __init__(self, parent, choices):
        super().__init__(parent)
        self.setWindowTitle('Compare Two Configurations')
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setSpacing(10)
        intro = QLabel('Choose a saved configuration and what to compare it with: another saved configuration or a '
                       'backup of the scanner. Nothing is changed in either.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(8)
        self.first, self.second = QComboBox(), QComboBox()
        for combo in (self.first, self.second):
            combo.setMinimumContentsLength(36)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumHeight(max(32, int(combo.sizeHint().height())))
        for label, folder in choices:
            if not label.startswith('Scanner backup '):
                self.first.addItem(label, folder)
            self.second.addItem(label, folder)
        form.addRow('Configuration', self.first)
        form.addRow('Compare with', self.second)
        layout.addLayout(form)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText('Compare')
        layout.addWidget(buttons)
        if len(choices) > 1:
            self.second.setCurrentIndex(1)            # the next configuration, not the same one twice
        self.first.currentIndexChanged.connect(self.changed)
        self.second.currentIndexChanged.connect(self.changed)
        self.changed()
        self.adjustSize()

    def changed(self, _index=None):
        same = self.first.currentData() == self.second.currentData()
        self.ok.setEnabled(bool(self.first.currentData()) and bool(self.second.currentData()) and not same)
        self.status.setText('Choose two different ones.' if same else '')

    def chosen(self):
        return ((short_name(self.first.currentText()), self.first.currentData()),
                (short_name(self.second.currentText()), self.second.currentData()))


class CompareMixin:
    """Menu actions for the main window."""

    def compare_two_configurations(self):
        """File → Compare Two Configurations… (v0.1.38): two saved configurations, or one and a scanner backup."""
        title = 'Compare Two Configurations'
        import scanner_backup
        import scanner_configurations
        open_folder = getattr(self, 'active_scanner_configuration', None)
        try:
            choices = comparison_choices(scanner_configurations.list_configurations(),
                                         scanner_backup.list_backups(), open_folder)
        except OSError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        if sum(1 for label, _f in choices if not label.startswith('Scanner backup ')) < 1 or len(choices) < 2:
            QMessageBox.information(self, title, 'There is nothing to compare yet: save at least two '
                                    'configurations, or one configuration and a scanner backup.')
            return
        dialog = ChooseComparisonDialog(self, choices)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        (first_name, first), (second_name, second) = dialog.chosen()
        if open_folder is not None and Path(first).resolve() == Path(open_folder).resolve() \
                and hasattr(self, '_modified_list_names') and self._modified_list_names():
            if QMessageBox.question(self, title, 'The open configuration has changes that are not saved. The '
                                    'comparison uses the saved version.\n\nSave the changes first?') \
                    == QMessageBox.StandardButton.Yes:
                self.save_draft_to_configuration()
        sides = cc.configuration_sides(first_name, second_name)

        def done(result, error):
            if error or not result:
                QMessageBox.warning(self, title, error or 'The comparison produced no result.')
                return
            CompareDialog(self, result, first_name).exec()
        self._run_background(title + ' — in progress', 'Reading both (read only)…',
                             lambda: cc.compare(first, second, sides), done)

    def compare_configuration_with_scanner(self):
        folder = getattr(self, 'active_scanner_configuration', None)
        if folder is None:
            QMessageBox.information(self, 'Compare with Scanner',
                                    'Open a scanner configuration first (File → Open Scanner Configuration…).')
            return
        unsaved = self._modified_list_names() if hasattr(self, '_modified_list_names') else []
        if unsaved:
            box = QMessageBox(self)
            box.setWindowTitle('Compare with Scanner')
            box.setText('These Favorites Lists have changes that are not saved:\n\n  ' + '\n  '.join(unsaved[:12]))
            box.setInformativeText('The comparison uses the saved configuration. Save the changes first?')
            save = box.addButton('Save, then Compare', QMessageBox.ButtonRole.AcceptRole)
            saved_only = box.addButton('Compare Saved Version', QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is save:
                self.save_draft_to_configuration()
                if self._modified_list_names():
                    return
            elif box.clickedButton() is not saved_only:
                return
        scanner = self.pick_scanner_folder('Compare with Scanner — choose the SDS100 SD card (read only)')
        if not scanner:
            return
        if self._scanner_operation_running('a comparison'):
            return
        self._db_update_busy = True
        name = Path(folder).name

        def done(result, error):
            self._db_update_busy = False
            if error or not result:
                QMessageBox.warning(self, 'Compare with Scanner', error or 'The comparison produced no result.')
                return
            CompareDialog(self, result, name).exec()
        self._run_background('Compare with Scanner — in progress',
                             'Reading the scanner and the configuration (read only)…',
                             lambda: cc.compare(folder, scanner), done)


class CompareDialog(QDialog):
    def __init__(self, parent, result, name):
        super().__init__(parent)
        self.comparison, self.name, self.host = result, name, parent
        self.sides = sides = result.get('sides') or cc.SCANNER_SIDES
        self.scanner_mode = sides['mode'] == 'scanner'
        self.setWindowTitle('Compare with Scanner — ' + name if self.scanner_mode
                            else f'Compare {sides["New"]} with {sides["Old"]}')
        self.resize(1000, 680)
        layout = QVBoxLayout(self)
        headline, lines = cc.summary(result)
        top = QLabel('<b>%s</b>' % headline + ('<br>' + '<br>'.join('• ' + l for l in lines) if lines else ''))
        top.setTextFormat(Qt.TextFormat.RichText)
        top.setWordWrap(True)
        layout.addWidget(top)
        mine_db, their_db = result['database']
        if mine_db or their_db:
            if self.scanner_mode:
                text = ('Master database — scanner: %s; configuration copy: %s. Export to Scanner never changes '
                        'the master database.' % (their_db or 'unknown', mine_db or 'unknown'))
            else:
                text = 'Master database — %s: %s; %s: %s.' % (sides['Old'], their_db or 'unknown', sides['New'],
                                                              mine_db or 'unknown')
            info = QLabel(text)
            info.setWordWrap(True)
            layout.addWidget(info)
        hint = QLabel('Scanner and Configuration columns show the value on each side; exporting this '
                      'configuration would change the scanner to the Configuration value.' if self.scanner_mode else
                      f'The two right-hand columns show the value in {sides["Old"]} and in {sides["New"]}.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        options = QHBoxLayout()
        self.hide_same = QCheckBox('Hide Favorites Lists that are the same')
        self.hide_same.setChecked(not result['identical'])
        self.hide_same.toggled.connect(self.fill)
        options.addWidget(self.hide_same)
        expand = QPushButton('Expand All')
        expand.clicked.connect(lambda: self.tree.expandAll())
        collapse = QPushButton('Collapse All')
        collapse.clicked.connect(lambda: self.tree.collapseAll())
        options.addStretch(1)
        options.addWidget(expand)
        options.addWidget(collapse)
        layout.addLayout(options)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Item', sides['Old'], sides['New']])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        copy = buttons.addButton('Copy Report', QDialogButtonBox.ButtonRole.ActionRole)
        copy.clicked.connect(self.copy_report)
        save = buttons.addButton('Save Report…', QDialogButtonBox.ButtonRole.ActionRole)
        save.clicked.connect(self.save_report)
        if self.scanner_mode and not result['identical'] and hasattr(parent, 'export_to_scanner'):
            export = buttons.addButton('Export to Scanner…', QDialogButtonBox.ButtonRole.ActionRole)
            export.setToolTip('Close this window and start File → Export to Scanner (preview first, as always)')
            export.clicked.connect(self.export)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.fill()

    # ------------------------------------------------------------ tree
    def _node(self, parent, texts, bold=False, tip=''):
        item = QTreeWidgetItem(parent, [str(t) for t in texts])
        if bold:
            font = QFont(item.font(0))
            font.setBold(True)
            item.setFont(0, font)
        if tip:
            item.setToolTip(0, tip)
        return item

    def fill(self):
        self.tree.clear()
        result = self.comparison
        for l in result['lists']:
            if self.hide_same.isChecked() and l['status'] == 'same':
                continue
            scanner_counts, mine_counts = l.get('counts', ({}, {}))
            top = self._node(self.tree, ['%s — %s' % (l['name'], cc.status_text(l['status'], self.sides)),
                                         cc.count_text(scanner_counts) if l['status'] != 'configuration only' else '—',
                                         cc.count_text(mine_counts) if l['status'] != 'scanner only' else '—'],
                             bold=l['status'] != 'same', tip=l['filename'])
            if l['error']:
                self._node(top, ['Could not compare: ' + l['error'], '', ''])
            if l.get('note'):
                self._node(top, [l['note'], '', ''])
            if l['settings']:
                group = self._node(top, ['List settings (%d)' % len(l['settings']), '', ''])
                for line in l['settings']:
                    label, _, values = line.partition(': ')
                    old, _, new = values.partition(' → ')
                    self._node(group, [label, old.strip("'"), new.strip("'")])
            if l.get('moved'):
                self._node(top, ['Entries are in a different order', '', ''])
            if l.get('added'):
                group = self._node(top, ['%s (%d)' % (cc.cap(self.sides['in_new']), len(l['added'])), '', ''])
                for item in l['added']:
                    self._node(group, ['%s %s' % (cc.WORDS.get(item['kind'], item['kind']).capitalize(), item['label']),
                                       '—', 'present'])
            if l.get('removed'):
                group = self._node(top, ['%s (%d)' % (cc.cap(self.sides['in_old']), len(l['removed'])), '', ''])
                for item in l['removed']:
                    self._node(group, ['%s %s' % (cc.WORDS.get(item['kind'], item['kind']).capitalize(), item['label']),
                                       'present', '—'])
            if l.get('changed'):
                group = self._node(top, ['Changed (%d)' % len(l['changed']), '', ''])
                for item in l['changed']:
                    entry = self._node(group, ['%s %s' % (cc.WORDS.get(item['kind'], item['kind']).capitalize(),
                                                          item['label']), '', ''])
                    for label, old, new in item['fields']:
                        self._node(entry, [label, old, new])
                    entry.setExpanded(True)
            top.setExpanded(l['status'] == 'different')
        if result['order_changed']:
            self._node(self.tree, ['Favorites List order differs', '', ''], bold=True)
        if result['profile'] or result['profile_note']:
            group = self._node(self.tree, ['Scanner settings (profile.cfg)', '', ''], bold=True)
            for line in result['profile']:
                where, _, values = line.partition(' — ')
                label, _, values = values.partition(': ')
                old, _, new = values.partition(' → ')
                self._node(group, ['%s — %s' % (where, label), old.strip("'"), new.strip("'")])
            if result['profile_note']:
                self._node(group, [result['profile_note'], '', ''])
            group.setExpanded(True)
        for name, state in result['other_files']:
            if state != 'same' or not self.hide_same.isChecked():
                self._node(self.tree, [name, state, ''], bold=state != 'same')
        if not self.tree.topLevelItemCount():
            self._node(self.tree, [self.sides['same'], '', ''])
        self.tree.resizeColumnToContents(0)
        self.tree.setColumnWidth(0, min(int(self.tree.columnWidth(0)), 560))

    # ------------------------------------------------------------ actions
    def report(self):
        return '\n'.join(cc.report_lines(self.comparison, self.name)) + '\n'

    def copy_report(self):
        QGuiApplication.clipboard().setText(self.report())

    def save_report(self):
        import data_area                          # v0.1.34: straight into the data folder's reports
        try:
            other = 'scanner' if self.scanner_mode else self.sides['Old']
            path = data_area.unique(data_area.folder('reports'), data_area.safe_name(
                'Compare %s with %s %s.txt' % (self.name, other, data_area.stamp())))
            path.write_text(self.report(), encoding='utf-8')
        except OSError as exc:
            QMessageBox.warning(self, 'Save Report', str(exc))
            return
        data_area.show_saved(self, 'Save Report', path)

    def export(self):
        self.accept()
        self.host.export_to_scanner()
