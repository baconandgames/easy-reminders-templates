# Easy Reminder Templates - Development Notes

> Alpha software: this project is under active development. It may change
> behavior, config shape, install process, and Apple Reminders output before a
> stable release.

## Project Goal

Easy Reminder Templates is a small Python utility that generates Apple Reminders
items from reusable JSON templates.

The long-term goal is to make repeatable Reminders lists fast and nearly
frictionless while keeping the implementation simple and maintainable. Recipes
are the first use case, but the tool should remain broad enough for packing
lists, travel prep, chores, and other reusable list templates.

This is a local project stored in Git.

---

## Design Philosophy

- Keep the code simple and readable.
- Build incrementally.
- Prefer plain Python over unnecessary frameworks.
- Avoid premature abstraction.
- The JSON format should remain human-editable.
- Favor maintainability over cleverness.

Whenever possible, implement one small feature at a time.

---

## Current Technology

- Python 3
- Installable Python package
- questionary for terminal prompts
- Git
- Apple Reminders via EventKit
- macOS only

External libraries should stay limited and must clearly improve the project.

---

## Project Structure

```text
easy-reminder-templates/
├── .gitignore
├── README.md
├── DEVELOPMENT.md
├── pyproject.toml
├── config.json
├── listkit
├── bin/
│   └── reminders-helper.swift
├── templates/
│   ├── recipes/
│   │   └── classic-chili.json
│   └── lists/
│       └── beach-day.json
├── recipe_shopper/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── delivery.py
│   ├── formatter.py
│   ├── templates.py
│   ├── default_templates/
│   │   ├── recipes/
│   │   └── lists/
│   └── bin/
│       └── reminders-helper.swift
└── tests/
    ├── test_delivery.py
    ├── test_shop.py
    ├── test_config.py
    ├── test_formatter.py
    └── test_templates.py
```

Only create files when they become necessary.

---

## Current Feature Plan

### Phase 1

- Load templates from JSON.
- List available templates.
- Select a template.
- Ask for batch size, defaulting to `default_batch`.
- Ask whether to include on-hand items.
- Scale item quantities.
- Format item quantities nicely.
- Print the final list to the terminal.

### Phase 2

Integrate with Apple Reminders.

The generated reminders should:

- Append `[short_name]` to created reminders when configured.
- Target an existing Reminders list.
- Print a creation summary.

---

## Deferred Features

These have intentionally been postponed.

- Ingredient IDs
- Pantry inventory
- Store departments
- Multiple template databases
- Native macOS application
- Cloud synchronization

---

## Planned Follow-Up Work

Track completed alpha milestones separately from open roadmap items so old
planning notes do not read like unfinished work.

### Completed Alpha Milestones

- Installable `listkit` command through `pipx`.
- GitHub install and upgrade path tested on a clean Mac.
- Apple Reminders integration through EventKit.
- Textual app shell with main menu, screen headers, footer controls, and
  app-style navigation.
- Settings menu for visible Reminders lists, colors, defaults, and updates.
- GitHub Releases update checker with changelog display, skip-current-version,
  and copied manual update command.
- One JSON file per template.
- Recipe templates with quantities, units, batch scaling, and on-hand items.
- Basic list templates without quantities or units.
- Create-template-from-existing-Reminders-list flow.
- Empty Reminders lists can create shell template JSON files with a blank item
  placeholder.
- Empty/no-visible-Reminders-list flow that prompts for a new list instead of
  showing an empty picker.
- Bundled examples for recipes, packing/travel, and recurring store purchases.

### Update Checking

Update awareness belongs in Settings, not in the normal add-items flow.
The implemented baseline checks GitHub Releases, shows release notes, prints the
manual update command, and allows a user to skip the current release.

For `pipx upgrade easy-reminder-templates` to pick up changes from GitHub, the
package version in `pyproject.toml` must increase. Until a release process is
formalized, bump the version for any pushed change that testers should receive
through `pipx upgrade`.

Current behavior:

- On opening Settings, quietly check GitHub Releases once per app session.
- If no newer version exists, keep the row as `Check for Updates`; after the
  user manually checks, update it inline to `Check for Updates: up to date`.
- If an update check fails after a manual check, update the row inline to
  `Check for Updates: unavailable`.
- If a newer version exists, show the settings row as `Update to vX.Y.Z`.
- Opening that item shows the available version, release notes, and choices:
  - show the manual update command
  - skip this version
  - back
- Start with a manual update command rather than self-updating:
  `pipx upgrade easy-reminder-templates`
- Store skipped versions in config so a skipped version stays quiet, but a newer
  version appears later.

Future improvement:

- Cache the update check result for about a day so Settings stays fast.
- Add lightweight startup update awareness without checking GitHub on every
  launch. Store `last_update_check_at` and possibly
  `launch_count_since_update_check` in `config.json`. On normal `listkit`
  startup, check only when either:
  - the last check was more than about 30 days ago, or
  - the app has launched about 10 times since the last check.
- If a startup check finds an update, show a small non-blocking notice that
  points users to Settings. Keep the full changelog,
  skip, and copied update-command flow inside config.

Do not make the app run `pipx upgrade` automatically in the first version of
this feature. Automatic updates can be considered later, but they add more
failure modes around permissions, shell environment, rollback, and support.

### Release Checklist

Use this checklist whenever publishing a version that testers should be able to
install or upgrade to with `pipx`.

1. Decide the next version number.
2. Update `version` in `pyproject.toml`.
3. Run the test suite:

```sh
PYTHONPATH=. pytest
```

4. Verify the source version:

```sh
PYTHONPATH=. python -m recipe_shopper.cli --version
```

5. Commit the version bump and code/docs changes.
6. Push `main`.
7. Create a GitHub Release whose tag exactly matches the package version:
   `v0.1.9` for package version `0.1.9`.
8. Confirm the release tag points at the commit containing that same
   `pyproject.toml` version.
9. On a test Mac, run:

```sh
pipx upgrade easy-reminder-templates
listkit --version
```

The version shown by `listkit --version`, the GitHub Release tag, and
`pyproject.toml` should all match.

Important: GitHub Releases and Python package metadata are separate. The update
checker reads GitHub Releases, but `pipx upgrade` installs package metadata from
the tagged commit. If a release tag says `v0.1.9` but `pyproject.toml` still says
`0.1.8`, `listkit` will detect `0.1.9` but `pipx upgrade` will remain on
`0.1.8`.

Test releases can be deleted after validation. Delete both the release and the
tag when cleaning up test-only versions.

### Textual Terminal App UX

`listkit` now uses a Textual app shell instead of the old linear prompt flow.
The goal is to feel like a small terminal application while still running fully
inside Terminal.

Current top-level menu:

- Add from Template
- Create Template from List
- Settings
- Help
- ⏻ Quit

Each screen should keep a consistent shape:

- orange title
- short blue status/context line
- body/menu
- orange footer controls, such as `[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]`

Visible navigation rows should use **↩ Back**. App exit should use **⏻ Quit**.
Avoid adding dead-end informational screens when inline feedback or a recoverable
picker state will do.

### Template Storage Model

Templates now use one JSON file per template.

Current shape:

```text
~/Library/Application Support/Easy Reminder Templates/
├── config.json
├── templates/
│   ├── recipes/
│   │   ├── classic-chili.json
│   │   └── tacos.json
│   └── lists/
│       ├── beach-trip.json
│       └── business-trip.json
└── backups/
```

Reasons for this direction:

- Editing one template should not risk corrupting the whole library.
- One broken template file should not prevent unrelated templates from loading.
- Individual templates are easier to copy, share, sync, diff, and recover.
- Future template types can evolve without forcing one large schema to carry
  every possible field.
- Migrations can run per file and create per-file backups.

Each template file should include a `schema_version`. Future migrations should
back up the file before writing changes. If one migration fails, the app should
report that template and continue loading the rest when possible.

### Generic Template Schema

Recipes are the first use case, but templates now support both recipe-style
items and plain checklist items.

A generic item supports list entries that do not need quantity or unit:

```json
{
  "name": "Passport",
  "always_on_hand": false
}
```

Recipe templates can keep using quantity/unit, while packing lists or general
checklists can use plain names. `always_on_hand` defaults to `false` when
omitted.

### Create Template from Existing Reminders List

Implemented as an app-level action in the main `listkit` flow:

```text
Create Template from List
```

Current flow:

1. Show available Apple Reminders lists.
2. Let the user select a source list.
3. Read incomplete reminders from that list.
4. Ask for a template name and optional short name.
5. Save a new list template file under `templates/lists/`.

If the selected Reminders list is empty, create a shell template with one blank
item placeholder. Blank placeholder items are valid in JSON but are ignored at
runtime until named. If a user selects a template with no named items, return to
template selection with a warning instead of entering the add-items flow.

Initial scope should stay conservative:

- Ignore completed reminders by default.
- Flatten sections unless preserving sections becomes clearly necessary.
- Omit notes, URLs, due dates, tags, and priorities in the first version.
- If a template name already exists, prompt to replace, rename, or cancel.

Future improvement:

- Consider whether this should also be available from a dedicated template
  management screen after the Mole-style app-shell decision.

### Reminders List Identity and Recovery

Keep using Reminders list IDs as the durable target identity, with list names as
cached display text.

Current behavior:

- If the ID exists but the name changed, silently update the cached name.
- If the ID is missing, fall back to matching the stored name.
- During normal `listkit` runs, show the Reminders list picker before sending so
  stale config can be corrected before writing anything.
- If no visible Reminders lists are available, prompt for a new list name.

Future improvements:

- When `listkit config` loads the default Reminders list setting, validate the
  stored list ID against current Reminders lists.
- If the stored ID is missing but the stored name has one match, save that new ID.
- If the stored name has multiple matches or no matches, prompt the user to
  choose or create a list.
- If Reminders itself has no lists, consider offering:
  - create a list using the template name
  - enter a different list name
  - cancel

Do not default to the short name for new list creation. Short names are intended
as compact tags and may not be user-facing enough.

### Stable Alpha Checklist

Before asking outside testers for broader feedback:

- Confirm sample templates communicate the three main use cases clearly:
  recipes, packing/travel, and recurring store purchases.
- Do a clean install on at least one Intel Mac and one Apple Silicon Mac.
- Test first-run Reminders permission behavior.
- Test update checking against a real GitHub Release.
- Test creating a list from each bundled sample.
- Test creating a template from a real Reminders list.
- Review README and template docs from a new-user perspective.
- Decide whether to keep the current prompt flow for alpha feedback or move
  first toward the Mole-style app shell.

### Config Migrations Before v1.0

Current alpha config changes should remain additive whenever possible. Existing
user settings should be preserved during upgrades, and missing settings can keep
falling back to defaults.

Before a stable v1.0 release, add explicit config versioning and migrations if
we introduce structural config changes.

Migration triggers:

- Renaming config keys.
- Splitting one setting into multiple settings.
- Combining multiple settings into one structured object.
- Changing the meaning or accepted format of a setting.
- Moving Apple Reminders settings into a broader multi-app structure.
- Changing template storage from a single file to per-template files.

Recommended migration behavior:

- Add a `schema_version` field to app-owned config and template files.
- Back up each file before writing a migrated version.
- Keep additive defaults simple: missing optional fields should be filled in
  without forcing a migration prompt.
- Preserve unknown fields when possible until v1.0 removes or formalizes them.
- If a migration cannot safely infer intent, prompt the user instead of
  guessing.
- Document each migration in release notes so support/debugging has a paper
  trail.

### Local Backups and Restore

Add backups for local app-owned data, not full Apple Reminders restore.

Back up:

- `config.json`
- per-template JSON files

Backup before:

- config editor saves
- template edits
- schema migrations

Suggested structure:

```text
~/Library/Application Support/Easy Reminder Templates/
├── config.json
├── templates/
└── backups/
    ├── config/
    │   └── 2026-08-21-143012-config.json
    └── templates/
        └── 2026-08-21-143012-classic-chili.json
```

Retention should be simple, such as keeping the last 10 backups per file.

A future `Restore from Backup` Settings item can restore app-owned files.
Avoid promising full Apple Reminders restore. A safer Reminders-specific feature
would be `undo last creation`, based on a log of the exact reminder IDs or item
names created by the most recent run.

---

## Coding Preferences

- Use type hints.
- Keep functions small.
- Separate business logic from Apple-specific code.
- Prefer `pathlib.Path`.
- Raise clear exceptions rather than silently failing.
- Don't over-engineer.

---

## Workflow

Implement one feature at a time.

A typical cycle should be:

1. Implement a small feature.
2. Verify it works.
3. Review together.
4. Commit.
5. Move to the next feature.

Favor many small commits over large ones.
