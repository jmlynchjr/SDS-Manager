# SDS-Manager User Manual

Version 0.1.41 · by J. Lynch, developed with the help of AI (Anthropic's Claude) · [PDF with each release](https://github.com/jmlynchjr/SDS-Manager/releases)

Use the outline button (☰) at the top right of this file to jump to a chapter.

## About this manual

This manual describes **SDS-Manager version 0.1.41**, a Linux program for managing a Uniden SDS100 scanner's Favorites Lists, settings and system database from a PC, without Sentinel. It also works with the SDS150.

Chapters 1 to 4 cover installing, the main window and scanner configurations, and are worth reading first. Chapter 10, *Exporting to the scanner*, explains how changes reach the scanner and how they are protected. The rest can be read as you need them.

### Conventions

- **Bold** names a button, menu item, window or setting as it appears on screen, for example **Save Configuration** or **Favorites → Keys & Tags…**.
- An arrow (→) shows a path through menus: **File → Export to Scanner…** means open the File menu and choose Export to Scanner….
- `Monospace` shows something you type, a file or folder, such as `~/.local/share` or `f_list.cfg`.
- `~` means your home folder, for example `/home/yourname`.
- An ellipsis (…) on a button or menu item means it opens a window or dialog.

> [!NOTE]
> Notes give background that helps explain why something works the way it does.

> [!TIP]
> Tips suggest a quicker or better way to do something.

> [!CAUTION]
> Cautions mark something that changes the scanner or can't easily be undone.

### About SDS-Manager

SDS-Manager was created by **J. Lynch**, developed with the help of AI (Anthropic's Claude) and tested on a real SDS100. AI was also used to help write this manual.

It is **free software** under the GNU General Public License version 3 or later: you may use, share and change it under the licence's terms. The source, the releases and the version history are at **github.com/jmlynchjr/SDS-Manager**.

SDS-Manager is an independent program. It is not made, endorsed or supported by Uniden or RadioReference. Uniden, SDS100, SDS200 and Sentinel are names and trademarks of their owners; RadioReference is a trademark of RadioReference.com LLC. The program follows Uniden's *SDS Series File Specification V2.00* and is provided as is, without warranty. Use it at your own risk.

Laws on listening to radio communications differ between places. You are responsible for using the scanner and this program lawfully.

## 1. Introduction

### What SDS-Manager does

SDS-Manager works with the files on the SDS100's memory card, the same files Sentinel uses. With it you can:

- **build Favorites Lists** from the RadioReference database, keep them up to date with RadioReference, or type systems, departments, channels and talkgroups in by hand;
- **edit lists**: names, frequencies, tones, avoids, attenuators, delays, alerts and the rest of each channel's settings; cut, copy and paste between lists; change many channels at once;
- manage **quick keys, number tags and scanning** in one window (Keys & Tags), with scan profiles, a LibreOffice spreadsheet and a printable key card;
- change the **scanner's settings**: global, search, weather, display, display layouts and colours, hardware, GPS and location, and service types;
- rebuild Uniden's **system database** from an archive and update the scanner with it, and put new **firmware** on the card for the scanner to install;
- **compare** the open configuration with what is on the scanner, or with another configuration or a backup, item by item;
- **export** everything to the scanner with checks, a backup first, and automatic recovery if a write fails;
- work with **SDS100 Monitor**: open what you hear in SDS-Manager, see how often each channel was heard, add the talkgroups it heard, set the attenuator where it suggests, put the Monitor's unit names on the scanner, and share quick key names and scan profiles.

### What you need

- A PC running Linux with Python 3.10 or newer and PyQt6. The program is developed on **Kubuntu**; the install steps here are for Kubuntu and other Debian- and Ubuntu-based systems.
- A Uniden **SDS100** or **SDS150** and its USB cable. The program is written for the SDS100; the SDS150 is accepted too (confirmed by a user). Other models are refused.
- For database contents: a RadioReference **Premium** account (chapter 5).
- For a database update: a Uniden master database archive (`MasterHpdb_MM_DD_YYYY.gz`) (chapter 9).
- Recommended: `python3-keyring` (keeps your RadioReference password in KDE Wallet or GNOME Keyring) and `python3-openpyxl` (the Keys & Tags spreadsheet). The package installs both when it can.

### How it works

SDS-Manager never edits the scanner directly. It keeps **scanner configurations**: copies of the scanner's files on your computer.

1. **Import from Scanner…** copies the scanner's configuration into SDS-Manager's library.
2. Every change you make goes into that copy. The scanner isn't touched.
3. **Save Configuration** keeps your changes in the copy.
4. **Export to Scanner…** compares the copy with the card, shows what will change, backs the card up, writes only what changed, and checks every file it wrote.

> [!NOTE]
> Before anything is written, every changed file is checked against Uniden's file specification and against real files from a working SDS100. A change SDS-Manager doesn't fully understand is refused, not guessed at.

## 2. Installing

### Install the package (recommended)

1. Download `sds-manager_<version>_all.deb` from the project's releases page, **github.com/jmlynchjr/SDS-Manager/releases**.
2. In a terminal, in the folder you downloaded it to:

   `sudo apt install ./sds-manager_0.1.41_all.deb`

apt installs PyQt6 and the other packages it needs. **SDS-Manager** appears in the application menu, and `sds-manager` starts it from a terminal. The program is installed in `/opt/sds-manager`. Your configurations, databases, backups and settings live in your home folder, not in the program folder, so installing a new version or removing the program never touches them.

**Personal and public editions:** the packages `sds-manager-personal` and `sds-manager` replace each other, so only one is installed at a time, and both replace the old `sds100-manager` package. Your data stays when you swap. **Help → About…** shows *(personal build)* in the personal edition.

### Updates

**Help → Check for Updates…** looks for a newer `sds-manager` package in `~/Downloads`, and on GitHub once you enter the repository (`jmlynchjr/SDS-Manager`) in its window, and installs it with **Install**.

### Removing it

`sudo apt remove sds-manager`

Your data stays in your home folder.

### Building from source

The source on GitHub runs with `./launch.sh` from its folder, or installs for the current user with `./install.sh`. The RadioReference application key is not in the source; the release packages include it. If you run SDS-Manager from source, enter your own RadioReference application key under **Advanced** in **Tools → RadioReference Account…**.

The automated tests run with `python3 -m unittest discover -s .` in the source folder.

## 3. The main window

### Panels

- **Database Contents** (left): the RadioReference database, browsed by country, state and county (chapter 5). Select a system to see its departments, channels and talkgroups, and use **Add to Favorites** to put them in a list.
- **Favorites Lists** (right): the lists of the open scanner configuration, in the scanner's order, with each list's systems, departments and channels. The **Favorites List** dropdown picks the list; the **Keys / Tag** column shows quick keys and number tags (for example *Key 03 · Tag 12* beside a system, *Key 04* beside a department, *Tag 120* beside a channel).
- **Scanner panel** (right side; show or hide it from the Tools menu): when the scanner's card is mounted, it shows the model, firmware, database date, free space and number of lists, your backups and the open configuration, with buttons for the common jobs. Detection only reads the card's identity files.

### The status bar

The bottom of the window shows the open configuration's name, with:

- **\*** when there are unsaved changes;
- **— not on scanner yet** when saved changes haven't been exported to the scanner (chapter 10). Hover over the name to see when the scanner last matched the configuration.

The bottom right shows whether the scanner's card is connected.

### Menus

| Menu | Contents |
|---|---|
| **File** | New, import, open, save, compare and export scanner configurations; Manage Configurations; Backup and Restore; Storage |
| **Edit** | Undo, Redo, Undo All Changes |
| **Favorites** | Everything about Favorites Lists, including Keys & Tags |
| **Database** | Open and search the local master database, rebuild it, and update the scanner's database |
| **Scanner Settings** | The scanner's settings, and Update Scanner Firmware |
| **Tools** | Settings, Find Everywhere, Name Unnamed Talkgroups, Check Heard Talkgroups with RadioReference, Search Frequency in RadioReference, RadioReference Account, Compare Local HPDB, Uniden Source Status, Theme |
| **Help** | User Guide, Recovery and Troubleshooting, What's New, Check for Updates, backups and log folders, licence and About |

Rarely used and read-only inspection tools are in **Advanced** submenus. A full list is in the appendix.

### Undo and redo

**Undo** and **Redo** (Ctrl+Z, Ctrl+Y, also on the Edit menu) work in the main window and the Favorites List editor. **Edit → Undo All Changes…** steps back through up to 40 remembered changes at once. Undo only affects the open configuration before you save; it never changes the scanner.

### Drag and drop

Drop the scanner's card folder on the main window to import it, or drop a `.hpd` list file to inspect it read-only.

### Saved files

SDS-Manager never asks where to save. Everything it makes goes into its data folder (chapter 14): lists saved as `.hpd` files, scan profiles, spreadsheets and key cards in `exports/`, comparison reports in `reports/`, and databases in `database/`. Each message names the file and has **Open Folder**. Nothing is overwritten: a second file with the same name becomes *Name (2)*. File choosers for files you bring in start in the matching data folder. **File → Storage → Open Data Folder…** opens it.

## 4. Scanner configurations

Everything you edit belongs to the open scanner configuration. You can keep several, for example one per scanner, or a spare to try ideas in.

### Import from the scanner

1. Connect the scanner to the PC with its USB cable and choose **Mass Storage** on the scanner. Its card appears as a removable drive.
2. **File → Import from Scanner…**. Choose the card's top folder, the one containing `BCDx36HP` (the detected card is offered first).
3. Give the configuration a name. SDS-Manager copies and checks the files, then opens it.

> [!TIP]
> Import again whenever the scanner was changed elsewhere (on the scanner itself, or in Sentinel), so you work from what the scanner really has.

### Open, save and save as

- **File → Open Scanner Configuration…** opens a saved configuration. If the open one has unsaved changes you are asked first (Save, Discard or Cancel).
- **File → Save Configuration** (Ctrl+S) keeps your changes.
- **File → Save Configuration As…** saves the open configuration under a new name.

### New scanner configuration

**File → New Scanner Configuration…** makes a configuration with the settings of one you choose (GPS, display, service types, search, alerts and so on) and no Favorites Lists. Add lists to it from the Favorites menu.

> [!CAUTION]
> Exporting a new configuration to the scanner it came from removes that scanner's current Favorites Lists. The export backs the scanner up first, and the old lists are kept in the backup.

### Compare with the scanner

**File → Compare Configuration with Scanner…** shows what differs between the open configuration and the scanner's card. It is read-only: nothing is written to the scanner or to the configuration.

- **Each Favorites List:** same, different, only in the configuration or only on the scanner, with counts of systems, departments, channels and talkgroups on each side.
- **Inside a list that differs:** the systems, sites, departments, channels, talkgroups and site frequencies found on only one side, and the ones changed, field by field (scanner value → configuration value). Avoids made on the scanner are marked as such when SDS-Manager knows the avoids from the last time the two matched.
- **Everything else:** Favorites List settings, list order, the scanner's settings (`profile.cfg`), `discovery.cfg` and the master database dates.

**Expand All** and **Collapse All** open or close the whole tree. **Copy Report** copies the comparison as text, **Save Report…** writes it to the data folder's `reports/`, and **Export to Scanner…** goes straight on to the export (chapter 10).

If the list has unsaved changes you are asked first: **Save, then Compare**, or **Compare Saved Version**.

> [!TIP]
> Compare before an export to see what the scanner has that the configuration doesn't, for example changes made on the scanner itself or in Sentinel.

### Compare two configurations

**File → Compare Two Configurations…** compares two configurations you have saved, or a configuration with one of the scanner backups SDS-Manager made before a write (chapter 14). Choose the **Configuration** and what to **Compare with**: the open configuration is offered first, then the others by name, then the scanner backups, newest first.

The same window as Compare with the Scanner shows what is only in one, only in the other, or different, with the two names as the column headings. **Copy Report** and **Save Report…** work the same way. Nothing is written to either side. If the open configuration has unsaved changes, you are offered to save them first.

> [!TIP]
> Comparing with the backup taken before an export shows exactly what that export changed on the scanner.

### Manage configurations

**File → Manage Configurations** has **Rename**, **Delete** and **Validate Scanner Configuration…**. Validate checks every file of a configuration against its saved checksums and Uniden's file rules, and changes nothing.

## 5. RadioReference

Database Contents comes from the **RadioReference** database, live, through your own RadioReference account.

### Your account

**Tools → RadioReference Account…** signs SDS-Manager in with your own RadioReference account, which needs an active **Premium** subscription.

1. Enter your username and password.
2. Press **Save and Test Sign-in**. It shows your username and when your Premium subscription ends.

- Your password is kept in KDE Wallet or GNOME Keyring (through `python3-keyring`), never in a settings file. Without a keyring it is kept only until SDS-Manager closes. **Forget Saved Password** removes it.
- The **application key**, which identifies SDS-Manager to RadioReference, is built into the release package. Only a build without one (for example, run from source) shows an **Advanced** section for a key of your own.
- SDS-Manager talks to RadioReference directly from your computer, always over HTTPS.

> [!NOTE]
> RadioReference data is used only to build and update the Favorites Lists of your own scanner. It is kept in memory while SDS-Manager runs; only what you add to a list is saved, in your configuration.

### Browsing

1. Choose the country and state.
2. Choose the **County**:
   - **Statewide systems and agencies** lists the state's trunked systems and statewide agencies;
   - a county lists its own conventional frequencies (as one system, with RadioReference's categories as departments), its trunked systems and its agencies.
3. Choose a system. It is loaded when you choose it.

**All Systems / Conventional / Trunked** narrows the list, and the search box finds names in what is shown.

### Searching for a frequency

**Tools → Search Frequency in RadioReference…** shows what uses a frequency: conventional frequencies in a county (**Search County**) or the whole state (**Search Whole State**); choose the **State** and **County** in the window (they start as Database Contents' choice), and, with **Include trunked site frequencies** ticked, the site frequencies of the area's trunked systems (system, site, LCN, NAC or colour code). Searching a whole state with trunked sites reads every system's sites once, which takes a while the first time; they stay in memory until SDS-Manager closes.

**Add to Favorites List…** puts a conventional result into a list. SDS100 Monitor can open this window for the frequency it is hearing.

### Which systems can be used

Conventional systems can always be used. Trunked systems can be used when their type has a list confirmed working on a real SDS100:

- **P25**;
- **DMR**, with one frequency per site (each talkgroup keeps its timeslot) or several (Capacity Plus, Connect Plus, Tier III, written as MotoTrbo, as Sentinel does). Every frequency needs its logical channel number on RadioReference;
- **NXDN** in NEXEDGE format, with each frequency's channel number and RAN.

Other types (Motorola, EDACS, LTR, NXDN IDAS) show why they can't be used yet. Talkgroups that RadioReference marks as fully encrypted are left out.

Talkgroup and channel names, frequencies, tones, NACs, colour codes, modes, service types and locations come from RadioReference. Everything else starts at the scanner's defaults.

### Updating a list from RadioReference

RadioReference changes over time: talkgroups are added, renamed or encrypted, and sites gain or lose frequencies. **Favorites → Update Favorites List from RadioReference…** compares the systems of the selected Favorites List with RadioReference as it is now, and you choose which changes to make. To check one system, right-click it in the list editor → **Update from RadioReference…**.

1. Choose the Favorites List in the main window, then open the window.
2. Each system of the list is shown with the RadioReference system it's linked to. A system added from RadioReference (with Add to Favorites, or in a new list) is linked already. For any other, press **CHOOSE…** and pick the state, county and system; the system with the same name is chosen for you. Trunked systems are listed under *Statewide systems and agencies* and under the counties they cover. The link is remembered, so you only do this once.
3. Tick the systems to check and press **CHECK FOR CHANGES**. SDS-Manager reads them from RadioReference, through your account.
4. The differences are listed by kind, each with a tick box:
   - **Trunked systems:** talkgroup names; talkgroup service type and DMR timeslot; new talkgroups; talkgroups no longer on RadioReference, or now fully encrypted; site frequencies added and removed; site NAC, channel numbers (LCN) and colour codes or RAN; new sites, and sites not on RadioReference.
   - **Conventional systems:** channel names; modulation, tone (CTCSS, DCS, NAC, colour code) and service type; new channels; channels no longer on RadioReference.
5. Check the ticks and press **APPLY TICKED CHANGES**. The window then offers to save the configuration; **Export to Scanner…** sends the changes.

**What is ticked to begin with:** new talkgroups and channels for departments the list already has, service types, tones, site frequencies, NACs and channel numbers, and names nobody chose (empty, a bare number, *TGID 1234* or the frequency itself). **Not ticked:** other name changes, because they may be names you gave; new departments; new sites; and anything that would delete. **TICK SUGGESTED**, **TICK ALL** and **UNTICK ALL** change them all, and each group's own box ticks or unticks everything in it.

- Only what you tick changes. Quick keys, number tags, avoids, alerts, delays, locations and the other settings of what's already in the list stay as they are.
- New talkgroups and channels go into the department with the same name, or into a new department named as on RadioReference. Like Add to Favorites, they take RadioReference's values and the scanner's defaults, with quick keys and number tags Off.
- A department never loses its last channel or talkgroup, a site its last frequency, or a system its last site. Anything held back for that reason is listed after Apply.
- All the changes are one Undo step, and they change only the open configuration. Nothing reaches the scanner until you export.

> [!NOTE]
> The links are kept in the data folder as `rr-links.json`. They hold only RadioReference's IDs and the system's name. What RadioReference sends is used for the comparison and then dropped; only the changes you apply are kept, in your configuration. If you rename a system in the list, choose its RadioReference system once more.

> [!TIP]
> Run **File → Compare Configuration with Scanner…** before an update, if the scanner may have been changed by hand. Then **Import from Scanner** first, so the update starts from what the scanner really has.

### Checking all lists at once

**Favorites → Check All Lists from RadioReference…** does the same for every Favorites List in the configuration, in one window: each linked system of each list, with the differences grouped under the list they belong to.

- The tick boxes, suggested ticks and safety rules are the same as for one list.
- A system that is in several lists is read from RadioReference only once.
- Systems that aren't linked yet are listed with **CHOOSE…**, as before. Lists made only of database entries (not scanner lists) are skipped.
- All the changes, in every list, are one Undo step, and the window offers to save the configuration.

## 6. Favorites Lists

### Making a list from the database

1. Open your configuration (**File → Open Scanner Configuration…**).
2. In **Database Contents**, select a system and use **Add to Favorites**.
3. Choose **Create a new Favorites List** to start a list from your selection, or add to an existing list.
4. For conventional systems, pick departments and channels. For trunked systems, pick site frequencies and talkgroups. Rectangle locations are supported in new lists.
5. **File → Save Configuration**, then **File → Export to Scanner…**.

New items take their information from the database, otherwise the scanner's default. Nothing is copied from another item, and two items never share a quick key or number tag.

### The Favorites menu

- **New Favorites List…** (Ctrl+N) asks for a name and what the list starts with: the system selected in the database, what you cut or copied in the list editor, or a conventional system you type in (system, department and first channel). A list always starts with at least one system.
- **Edit Favorites List…** (Ctrl+E) opens the list editor for the selected list.
- **Duplicate Favorites List…** copies a list under a new name. **Copy Favorites List to Another Configuration…** copies it into another saved configuration. Copies start with their quick key, number tag and startup keys Off, so they never clash with the lists already there.
- **Reorder Favorites Lists…**: drag the lists, or use Up and Down. The scanner shows them in that order after export.
- **Delete Favorites List…** removes a list. The file is kept in the configuration's backups.
- **Import Favorites List File (.hpd)…** adds a list file from anywhere (another scanner's card, a backup, a friend) after the same checks as any new list. **Save Favorites List as File (.hpd)…** writes the selected list to a file.
- **Favorites List Settings…**: each list's name, monitor state, quick key, number tag, startup keys and system quick-key flags.
- **Update Favorites List from RadioReference…** and **Check All Lists from RadioReference…**: the list's systems compared with RadioReference as it is now, with a choice of what to change (chapter 5).
- **Keys & Tags…** (Ctrl+K): chapter 7.

### The list editor

**Edit Favorites List…** opens the list in its own window. The left pane shows the list's systems, sites and departments; the right pane shows the channels or talkgroups of the department selected on the left, with all their settings.

- Change a value by double-clicking it, or select it and use **Edit Selected Field…**. Dropdowns offer only the values the scanner accepts. Reserved and unsupported fields are read-only and kept exactly.
- Right-click in the left pane to **Rename System…** or **Rename Department…**, or **Edit Site…** (a trunked site's settings, including its quick key, location, range and attenuator). Right-click a channel or talkgroup to edit its name, frequency or ID, or delete it.
- Quick keys and number tags of systems, departments and channels are set in Keys & Tags (chapter 7).
- **Heard (90 days)** and **Last Heard** show how often SDS100 Monitor logged each channel or talkgroup (chapter 11).
- Each change is one Undo step. **Save Configuration** keeps them.

#### Adding by hand

Right-click in the left pane:
- **New Conventional System…** (also on the empty area): system name, first department and first channel.
- **New Department…** on a system or department: a conventional department starts with one channel (name, frequency, modulation, tone); a talkgroup department starts with one talkgroup (name and ID).
- **Add Conventional Frequency…** on a conventional department: name, frequency, modulation and an optional tone, NAC or colour code. **Add Talkgroup…** on a talkgroup department.
- **Delete System…**, **Delete Department…** and **Delete Site…** remove them with everything in them, or select one and press **Delete**. A list can't be left empty, and a trunked system keeps at least one site.
- Select several channels or talkgroups on the right, or several systems, sites and departments on the left (Ctrl+click adds one, Shift+click a range), and press **Delete** to remove them together, as one Undo step.

Trunked systems come from the database, with their sites.

#### Cut, copy and paste

Right-click, or press Ctrl+X, Ctrl+C and Ctrl+V, in either pane:
- **Left pane:** a whole system, or a department with its channels or talkgroups. A talkgroup department brings its system's sites along, so it can start that system in a list that doesn't have it yet.
- **Right pane:** the selected channels or talkgroups (Ctrl+click or Shift+click to select several). Select the department to paste into in the left pane first.

To move something to another list, cut or copy it, close the window, open the other list with **Edit Favorites List…**, select where it goes and **Paste**:
- it goes into the selected conventional system, or into the same system (same name and type) if the list has it, or in as a new system;
- a department with the same name takes the new channels or talkgroups;
- anything already there is skipped, and nothing is replaced. You see what will be added before anything changes.

Talkgroups only go into a trunked system of the same type (P25 into P25, DMR into DMR). **Cut** removes the item at once, as one Undo step; paste it once. A copy can be pasted many times.

**Paste as New Favorites List…** (left pane) makes a new list holding what you cut or copied. For example, cut *City Police* from a county list and paste it as a new list called *City Police*.

When something you paste has a quick key or number tag already used in the list you paste into, Paste lists the clashes and asks:
- **Next Free Numbers** (the default) moves only the clashing ones to free numbers;
- **Set Them Off** clears them;
- **Keep Them** leaves them used twice; Keys & Tags will show them.

#### Changing several channels at once

Select rows (Ctrl+click or Shift+click the row numbers) and choose **Change Selected…**. Pick **Avoid**, **Attenuator**, **Delay** or **Volume Offset** and a value, and confirm once. The whole change is one Undo step.

## 7. Keys & Tags

**Favorites → Keys & Tags…** (Ctrl+K) is the one place for quick keys, number tags and what the scanner scans.

### Quick keys and number tags

- A **quick key** switches scanning On and Off. Favorites Lists, systems, departments and trunked sites can have one.
- A **number tag** jumps straight to a Favorites List, system or channel (on the scanner, or with SDS100 Monitor's Go to Number Tag).

They are separate settings: Favorites List quick key 1 is not number tag 1.

**Number sets:**

| Numbers | One set for | Range |
|---|---|---|
| Favorites List quick keys and number tags | the whole scanner | 0–99 |
| System quick keys and number tags | each Favorites List | 0–99 |
| Department and site quick keys | each system | 0–99 |
| Channel and talkgroup number tags | each system | 0–999 |

A trunked site's quick key is in the same set as its system's departments: switching that key Off stops both.

### The window

- The tree lists every Favorites List, with its systems, their sites and departments, and their channels and talkgroups.
- **Quick key** and **Number tag** show each item's numbers.
- **Scanning** says in words whether the scanner scans it, and why not. For example: *not scanned: department key 04 is Off*, or *not scanned: Favorites List Lakeside County has Monitor Off*.
- **Sorting:** click a column heading, or pick from **Sort:** (Scanner order, Name, Quick key, Number tag, Not scanned first, Detail). Items are sorted among their own level; **Scanner order** puts everything back.

### Changing numbers and switches

- Double-click a number. The list shows every number with *free* or *used by …*, plus **Next free**.
- Tick or untick **Scanning** to switch that key On or Off. Everything on the same key follows. Tick **Detail** on a list to switch its Monitor.
- **Number Keys in Order…** and **Number Tags in Order…** number everything under the selected item from a start number, counting up by a step. On a trunked system, **Number Keys in Order…** asks whether to number its departments, its sites, or both.
- **Next Free Key**, **Next Free Tag** and **Clear** work on the selected items.
- **Tags by Department…** (select a system) gives each department's channels a block of number tags, for example the 100s for the first department and the 200s for the next.
- **Match Tags to Keys** sets each number tag to the item's quick key, so you only remember one number.

Underneath, problems are updated as you work: numbers used twice in one set, items that won't be scanned because a key is Off, and Favorites List keys that are On with nothing on them.

### Scan profiles

A **profile** is a saved set of which keys are On and which lists are monitored, for example *Home*, *Fire only* or *Storm*.

- **Save Current as Profile…** saves the switches as they stand.
- **Use** sets them from a profile; **Apply** keeps them, and **Export to Scanner** sends them.
- Profiles go by list and system names. Lists added after a profile was saved are left as they are, and the window names them.
- Profiles are kept on your computer, not on the scanner. SDS100 Monitor can apply one to the scanner while it runs.

**Import…** and **Export…**, on the scan profile row, move profiles between configurations and computers:
- **Import** from another saved configuration, from a scan profiles file, or from the scanner's current keys. The last makes a new profile of which keys are On and which lists are monitored on the card (it only reads the card).
- Lists are matched by name, then by file number, so profiles carry over when the file numbers differ. Lists that aren't in this configuration are left out and named in the result.
- Choose which profiles to bring in. Names already used get *(2)* unless you choose to replace them.
- **Export** writes the chosen profiles, with their list names, to a `.json` file in the data folder's `exports/`.
- Imported profiles are shared with SDS100 Monitor straight away.

### Spreadsheet and key card

- **Save Spreadsheet…** writes a LibreOffice Calc spreadsheet with sheets for Favorites Lists, Systems, Departments (and sites) and Channels, plus a 00–99 map of Favorites List numbers. Numbers go in yellow cells; check columns turn red when two items in one set share a number. It needs `python3-openpyxl`; without LibreOffice it is saved as `.xlsx`, which Calc also opens.
- **Read Spreadsheet…** brings the numbers you edited back as changes to check and Apply. Rows that no longer match, and values that aren't whole numbers, are skipped and listed. Keep the hidden *Ref* column, and don't add or move rows.
- **Key Card (PDF)…** makes a printable page to keep with the scanner: list keys and tags, each monitored list's system and department keys, and a directory of channel number tags.

### Apply

**Apply** shows the changes in words first, then saves list keys, tags and switches to the configuration and puts system, department and channel changes into the lists, offering to Save Configuration. Two Favorites Lists can't share a key or tag, so Apply refuses that.

**Export to Scanner** shows the same warnings in its preview. They don't block the export.

## 8. Scanner settings

All under **Scanner Settings**. Each window shows only the settings it covers; **Save** shows the checked changes for review, then saves them to the configuration. **Export to Scanner…** sends them.

| Menu entry | Contents |
|---|---|
| **GPS and Location Settings…** | Location source, current location and saved locations |
| **Service Types…** | Which service types are scanned |
| **Global Settings…** | Global scanner options |
| **Search Settings…** | Common search, Close Call, Limit Search, Tone-Out, band defaults, Waterfall bands and colours, broadcast screens |
| **Weather Settings…** | Weather options and SAME groups |
| **Display Settings…** | Display options and backlight |
| **Display Layouts and Colours…** | The items on each screen row, and screen colours |
| **Hardware Settings…** | Battery, owner information, clock, recording, standby |

**Inspect Scanner Settings (Read-only)…** shows every setting without changing anything.

### Firmware

**Scanner Settings → Update Scanner Firmware…** puts new firmware on the scanner the way Sentinel does: it writes the files to the card's `BCDx36HP/firmware` folder, and the scanner installs them itself the next time it starts from its own card. SDS-Manager never flashes firmware itself.

1. Connect the scanner in mass-storage mode. The window shows the model and main firmware version from the card, and any files already waiting.
2. Download the firmware from Uniden's support page (info.uniden.com → SDS100 Firmware Update) and use **Add File…** with the `.zip`, `.bin` (main) or `.firm` (sub) file; zips are read without unpacking.
3. **Write to Scanner…** checks what is needed and shows exactly what will be written. Confirm, and the files are written and read back.
4. Eject the scanner in your file manager, then unplug the USB cable. The scanner checks each file, installs it and deletes it.

**Checks before writing:** the file is for exactly your model (an SDS100 never gets SDS100E or SDS200 firmware); at most one main and one sub file; a plausible size and not a saved web page; the identified SDS100 or SDS150 with enough free space; a second confirmation for an older main version. Firmware files already waiting in the folder are listed and removed first (you can keep them); other files there, such as the scanner's location tables, are left alone.

Firmware files are kept in the data folder's `firmware/`, with a receipt for each write. The card doesn't record the sub firmware version, so the window can't say whether a sub file is newer; the scanner shows both versions on its own screen.

> [!CAUTION]
> Don't turn the scanner off while it installs firmware. Follow its on-screen prompts.

## 9. The system database

The scanner keeps its own copy of Uniden's system database (the **master database**), which it uses for Full Database scanning and location-based scanning. SDS-Manager can replace it with a newer one.

1. **Database → Update Database (Rebuild from Archive)…**: choose a Uniden master database archive (`MasterHpdb_MM_DD_YYYY.gz`). SDS-Manager keeps a copy in its data folder and rebuilds the scanner's database files from it on your computer. This takes several minutes and doesn't touch the scanner.
2. Connect the scanner in mass-storage mode.
3. **Database → Update Scanner's Master Database…**: pick the rebuilt version, then the card's top folder.
4. A read-only check runs first. It shows the scanner's database date and the new one, and how many state files change. It refuses an older database, a different set of states, or a rebuild that doesn't match what the card holds.
5. Confirm. SDS-Manager backs up, writes only the files that changed (`hpdb.cfg` last), checks them, and tells you where the backup is.

Your Favorites Lists, settings and every other file are not touched by a database update.

### The local database

The other entries on the Database menu work with the rebuilt database on your computer, never the scanner:

- **Open Database…** opens a rebuilt database, **Build Search Index** indexes every state, and **Search All States** searches all of them.
- **Import Local HPDB…** brings in a database folder you already have (for example a copy from a card) after checking it, into the data folder.
- **Database Information** shows the database's version and files.

**Tools → Compare Local HPDB…** compares two local copies without changing either, and **Tools → Uniden Source Status** checks Uniden's software page (it is not a database update check). **Database → Advanced** holds the validation tools, **Export One State File…** and **Rebuild Full Database to a Folder…**, which write to the data folder's `database/rebuilt/`.

## 10. Exporting to the scanner

**File → Export to Scanner…** sends the saved configuration to the scanner.

1. Save your changes (**File → Save Configuration**).
2. Connect the scanner in mass-storage mode and choose **Export to Scanner…**. Choose the card's top folder.
3. If avoids on the scanner differ from the configuration, you are asked about them first (below).
4. The preview lists in plain words what will change (new, removed and edited lists, changed settings, keys and tags that clash or switch things off), then the file-by-file details.
5. If it says **READY**, confirm. If it says **BLOCKED**, the reason is shown and nothing has changed.
6. When it finishes, eject the card in your file manager and wait for it to finish before unplugging or switching the scanner on.

What the export does:
- checks that the card belongs to the identified SDS100 or SDS150 on USB, isn't read-only, and has room;
- makes a fresh backup of the card's configuration and checks it (SHA-256) before writing anything;
- writes only the files that changed, staging and checking each one, and restores every changed file automatically if anything fails part way.

> [!CAUTION]
> Unplugging or switching off before the card has finished ejecting can leave a file empty on the card. If that happens, run the export again.

### Avoids made on the scanner

A permanent avoid set on the scanner itself, or from SDS100 Monitor, is stored on the scanner. A configuration saved earlier still has the old setting, so exporting it would undo the avoid.

Before an export, SDS-Manager compares the avoids of systems, sites, departments, channels and talkgroups on the scanner with the configuration's. Any that differ are listed with tick boxes:

- **Keep Ticked and Continue** saves the ticked avoids into the configuration, then goes on with the export;
- **Continue Without** exports the configuration as it is; **Cancel** stops.

Ticked to begin with: those changed on the scanner since it last matched the configuration. Avoids you changed in SDS-Manager aren't listed; your change is exported. Until a configuration has been read from or exported to the scanner once, SDS-Manager can't tell which side changed, and ticks the ones the scanner has avoided.

### Is the scanner up to date?

SDS-Manager remembers when the scanner last matched each configuration: after **Import from Scanner…** and after each successful export. If you save changes and don't export them, the status bar says **— not on scanner yet**, and SDS100 Monitor shows a warning.

## 11. Working with SDS100 Monitor

[SDS100 Monitor](https://github.com/jmlynchjr/SDS-MONITOR) controls the scanner live over USB. With both installed:

### From the Monitor

- **Edit in Manager…**: right-click a reception in the Monitor (or use **Tools → Edit Current Channel in Manager…**). SDS-Manager opens the list editor on that talkgroup or channel. If it is in several places you choose one; with no configuration open you are offered one.
- **Add to Favorites List in Manager…**: right-click a reception. SDS-Manager asks which department to put it in (the same department and system come first, marked ★), and for a name, and for channels the modulation and an optional tone. It is one Undo step; Save Configuration keeps it. This works for Close Call, search and Discovery hits, and for talkgroups heard through ID Search.
- **Check Heard Talkgroups:** the Monitor's **Tools → Check Heard Talkgroups in SDS-Manager…** (the last 30 days), or the link under *Talkgroups and channels not heard in the previous 30 days* in its daily, weekly and monthly reports (the days of that report), opens **Check Heard Talkgroups with RadioReference** here (below).
- **Attenuator:** the Monitor's **Tools → Signal and Attenuator…** (1.1.113 or later) says where the attenuator helps or hurts, for a trunked site or a conventional channel. Right-click there, or press **SET IN SDS-MANAGER** after its attenuator test, to send it here. SDS-Manager lists every place it would change: the site of that name in the same system (every site of the system when the Monitor didn't know which), or every conventional channel on that frequency (only the same system's when it has one), each with its setting now. Untick any to leave; **CHANGE** sets them as one Undo step. Save Configuration keeps it, and Export to Scanner sends it, so the export no longer undoes an attenuator you only set on the scanner.

For each of these, SDS-Manager comes to the front (it is started if it isn't running), and offers to open a configuration if none is open.

### In SDS-Manager

- **Heard (90 days)** and **Last Heard**, the last two columns of the list editor, show how many times the Monitor logged each channel or talkgroup in the last 90 days, and when. Talkgroups are matched by system name and talkgroup ID, channels by frequency. Sort by them to find what's never on the air.
- **Add Unit Names from SDS100 Monitor…** (right-click a system in the list editor) puts the unit names you confirmed in the Monitor (not those marked Guess) into every trunked system in the list where the Monitor heard that unit. A unit already there with another name is renamed. It is one Undo step; Save Configuration and Export send it.
- **Tools → Name Unnamed Talkgroups…** suggests names for talkgroups that have none, from the database and from what the Monitor recorded. Tick, check and apply, as one Undo step.

> [!NOTE]
> Uniden's file specification doesn't fully say how the scanner stores unit IDs, so SDS-Manager copies a unit ID row the scanner wrote itself. If a system has none yet, add one unit ID on the scanner (in that system's Edit Unit IDs menu), import the configuration from the scanner again, and run Add Unit Names again.

### Check Heard Talkgroups with RadioReference

**Tools → Check Heard Talkgroups with RadioReference…** takes the talkgroups SDS100 Monitor heard and finds the ones this configuration's Favorites Lists don't have, or have with no real name (blank, just the ID, *TGID 44353*).

- **Heard in the last** 30 days to begin with (1–365); **RELOAD** reads the Monitor's history again. Talkgroups are matched by system name and TGID, as in the list editor's Heard columns.
- Each talkgroup shows its system, TGID, calls, when it was last heard, and whether it is **Not in your lists**, **In your lists, no name**, or on a **System not in your lists** (those can't be added: add the system first).
- **LOOK UP ON RADIOREFERENCE** reads each system's talkgroups and categories through the RadioReference system it is linked to, the same links as Update from RadioReference (chapter 5); **CHOOSE…** links a system that isn't linked yet. Each system is read once per session.
- It suggests the **name** (RadioReference's, as for lists built from RadioReference; otherwise the name the scanner showed), the **department** for a new talkgroup (the RadioReference category: the list's department of that name, or a new one; *Heard by Monitor* when there is no category) and the **service type**. Names and departments can be changed before applying.
- **Ticked to begin with:** talkgroups found on RadioReference that aren't fully encrypted. Fully and partly encrypted talkgroups are marked; talkgroups RadioReference doesn't have can be ticked and named by hand.
- **APPLY TICKED** adds the missing talkgroups (quick keys and number tags Off, like Add to Favorites) and names the unnamed ones, as one Undo step. Save Configuration and Export to Scanner as usual.

The Monitor's files are only read, and RadioReference is read live through your own account; nothing from it is stored.

### Shared with the Monitor

Whenever the configuration is saved or a profile changes, SDS-Manager writes `~/.local/share/sds100-database-favorites-manager/monitor-keys.json`. From it the Monitor:

- names its quick key buttons (systems, departments, and sites marked "(site)");
- lists tagged channels in **Go to Number Tag**;
- applies scan profiles to the scanner;
- warns when the scanner is out of date.

SDS-Manager only reads the Monitor's files in `~/SDS100Monitor`, and the two programs talk only on this computer.

## 12. Finding things

**Tools → Find Everywhere…** (Ctrl+F) searches the active master database and the Favorites Lists of the open configuration at once. Enter:

- a name (system, department, site, channel, talkgroup or list);
- a frequency in MHz: `154.9` finds everything from 154.900 to 154.999; `460.025` finds exactly that frequency;
- or a talkgroup ID.

Results show the type, value and the system › department they belong to. **Copy Results** copies the table. Searching never changes anything. Only the first 500 matches are shown, so narrow a very broad search.

## 13. Settings and themes

### Settings

**Tools → Settings…** (Ctrl+,):

- **Scanner connection:** where removable media appear, automatic detection, and offering the detected card in folder prompts.
- **Backups:** how many to keep when you clean up, and a size warning.
- **Confirmations:** low-risk prompts only. Writes to the scanner are always confirmed.
- **Database:** an optional startup check for a newer Uniden database (it contacts Uniden in the background and only reports; it never downloads), and how many rebuilt database versions to keep.
- **Appearance:** theme, accent colour, text size and an exact font size.
- **Log detail.**

**Tools → Preferences** chooses the columns shown in Database Contents and the Favorites Lists.

### Themes

**Tools → Theme** offers the same themes as SDS100 Monitor, applied at once:

- **Mode:** System (follow KDE), Dark, Light, or Night (red), dim red only to keep your night vision.
- **Accent:** Blue, Red, Green, Amber, Purple or Teal.
- **Text size:** Small, Normal, Large or Extra large.

## 14. Backups, storage and recovery

### Where things are kept

Everything SDS-Manager makes is kept in one data folder, `~/.local/share/sds100-database-favorites-manager/` (**File → Storage → Open Data Folder…** opens it):

| What | Where in the data folder |
|---|---|
| Scanner configurations | `scanner-configurations/` |
| Scanner backups | `scanner-backups/<date and time>/` |
| Database archives (downloaded, or a copy of the one you chose) | `database/downloads/` |
| Rebuilt databases | `database/versions/` (`database/current` is the one in use) |
| Rebuild Full Database and Export One State File | `database/rebuilt/` |
| Firmware files and write receipts | `firmware/` |
| Scan profiles | `scan-profiles/` |
| Saved lists (.hpd), exported profiles, spreadsheets, key cards | `exports/` |
| Comparison reports | `reports/` |
| Shared with SDS100 Monitor, export state | `monitor-keys.json`, `export-state.json` |
| Which RadioReference (or Uniden) system each list system comes from | `rr-links.json` (IDs and names only) |

Settings stay in `~/.config` and the log in `~/.local/state`, where Linux keeps them.

> [!NOTE]
> Before version 0.1.34 the databases and firmware were in a second folder, `~/.local/share/SDS100DatabaseFavoritesManager/`. The first time 0.1.34 or later starts, its contents are moved into the data folder, and the old name is left as a link, so SDS100 Monitor and anything else using the old path still finds the same files.

Each backup holds `BCDx36HP/` (the scanner's files as they were), `manifest.json` (every file with its SHA-256), `EXPORT_RECOVERY.txt` (which files the export changed) and `EXPORT_RESULT.json` (what was written). Backups are on your computer, not on the card. **File → Compare Two Configurations…** can compare a configuration with any of them (chapter 4).

**File → Backup and Restore → Back Up Scanner Configuration (Read-only)…** (or **Back Up Scanner Now…** on the Scanner panel) makes a backup without exporting. **Clean Up Old Backups…** on the Scanner panel, and cleaning up old database versions, are always manual and show exactly what will be deleted first; the newest backups, the current database and the one on your scanner are never offered.

### If something goes wrong

**SDS-Manager reports a failed write.** It restores every changed file from the backup by itself. If it says **DO NOT DISCONNECT**, leave the scanner connected and follow the message, which names the backup folder and the files to restore.

**The scanner misbehaves, or a list is empty after an export.**
1. Switch the scanner off. Connect it in mass-storage mode (or put the card in a card reader).
2. **File → Backup and Restore → Restore from Backup…** and choose the backup taken before that export. Follow the preview.
3. By hand instead: open the backup folder, read `EXPORT_RECOVERY.txt`, and copy each listed file from the backup's `BCDx36HP` folder back to the same place on the card. Delete any file marked as ADDED.
4. Eject the card, then switch the scanner on.

**A list or the database looks empty right after writing.** The card was almost always unplugged or switched off before it finished ejecting. Export again, wait for the eject to finish, then switch on.

**Export says BLOCKED.** Read the reason. Typical causes: the card isn't the recognised SDS100 or SDS150 on USB, it is read-only or too full, or a file on the card changed since the configuration was imported (import a fresh copy with **Import from Scanner…**).

**After a firmware update the scanner doesn't start or shows an error.** The scanner checks firmware before installing it and refuses a damaged or wrong file. Switch it off and on. If it keeps trying, connect it in mass-storage mode, delete everything in `BCDx36HP/firmware`, eject and start again.

**Last resort.** Copy the `BCDx36HP` folder from any backup over the card's `BCDx36HP` folder, or restore with Sentinel's own backup.

**Help → Copy Diagnostic Information** copies the version and system details (no scanner data) for a problem report.

## 15. Limits and reporting problems

### What SDS-Manager will and won't do

- It **will** replace the master database, add and remove Favorites Lists, edit existing lists, and change the checked scanner settings.
- It **will** place checked firmware files for the scanner to install. It never flashes firmware itself.
- It **won't** write anything it can't check.
- **Not yet supported** (waiting for real samples): new lists for Motorola, EDACS and LTR systems; IFX frequencies; editing avoid-frequency lists; adding a rectangle department to an existing list.

### Reporting problems

Report problems on the project's GitHub **Issues** page, with the message shown and **Help → Copy Diagnostic Information**.

If you use a system type that isn't supported yet, build the same list in Sentinel and send the `f_NNNNNN.hpd` and `f_list.cfg` it writes. Real Sentinel-written files are how each new type is checked.

## Appendix: menus

| Menu | Item |
|---|---|
| **File** | New Scanner Configuration…, Import from Scanner…, Open Scanner Configuration…, Save Configuration (Ctrl+S), Save Configuration As…, Compare Configuration with Scanner…, Compare Two Configurations…, Export to Scanner…, Exit |
| **File → Manage Configurations** | Rename, Delete and Validate Scanner Configuration… |
| **File → Backup and Restore** | Scanner Export Preflight (Read-only)…, Back Up Scanner Configuration (Read-only)…, Restore from Backup… |
| **File → Storage** | Import Existing Database into Managed Storage…, Open Data Folder… |
| **Edit** | Undo (Ctrl+Z), Redo (Ctrl+Y), Undo All Changes… |
| **Favorites** | New Favorites List… (Ctrl+N), Edit Favorites List… (Ctrl+E), Duplicate…, Copy to Another Configuration…, Reorder…, Delete…, Import Favorites List File (.hpd)…, Save Favorites List as File (.hpd)…, Favorites List Settings…, Update Favorites List from RadioReference…, Check All Lists from RadioReference…, Keys & Tags… (Ctrl+K) |
| **Favorites → Advanced** | Favorites List Relationships (Read-only)…, Inspect Native .hpd (Read-only)… |
| **Database** | Open Database…, Build Search Index, Search All States, Import Local HPDB…, Database Information, Update Database (Rebuild from Archive)…, Update Scanner's Master Database… |
| **Database → Advanced** | Validate Master HPDB…, Validate Master HPDB .gz…, Export One State File…, Rebuild Full Database to a Folder… |
| **Scanner Settings** | Inspect Scanner Settings (Read-only)…, GPS and Location…, Service Types…, Global…, Search…, Weather…, Display…, Display Layouts and Colours…, Hardware…, Update Scanner Firmware… |
| **Tools** | Settings… (Ctrl+,), Find Everywhere… (Ctrl+F), Name Unnamed Talkgroups…, Check Heard Talkgroups with RadioReference…, Search Frequency in RadioReference…, RadioReference Account…, Compare Local HPDB…, Uniden Source Status, Theme, Preferences, Advanced → Diagnostic Export Preview (Read-only)… |
| **Help** | User Guide (F1), Recovery and Troubleshooting, What's New (Change Log), Check for Updates…, Open Scanner Backups Folder, Copy Diagnostic Information, Open Log Folder, License, About… |
