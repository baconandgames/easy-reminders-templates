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

These are not part of the first install test. Revisit them after the GitHub
install path has been tested on a clean Mac.

### Update Checking

Update awareness belongs in `listkit config`, not in the normal `listkit` flow.
The implemented baseline checks GitHub Releases, shows release notes, prints the
manual update command, and allows a user to skip the current release.

For `pipx upgrade easy-reminder-templates` to pick up changes from GitHub, the
package version in `pyproject.toml` must increase. Until a release process is
formalized, bump the version for any pushed change that testers should receive
through `pipx upgrade`.

Current behavior:

- On opening `listkit config`, quietly check GitHub Releases.
- If a newer version exists, show the config menu item as `Check for Updates (1)`.
- Opening that item should show the available version, release notes, and choices:
  - show the manual update command
  - skip this version
  - back
- Start with a manual update command rather than self-updating:
  `pipx upgrade easy-reminder-templates`
- Store skipped versions in config so a skipped version stays quiet, but a newer
  version appears later.

Future improvement:

- Cache the update check result for about a day so the config menu stays fast.

Do not make the app run `pipx upgrade` automatically in the first version of
this feature. Automatic updates can be considered later, but they add more
failure modes around permissions, shell environment, rollback, and support.

### Mole-Style Terminal App UX

Revisit this after the core creation/config/template flows are more stable.

Current `listkit` behavior is a linear prompt flow: prompt, answer, prompt,
answer, print output. Longer term, the CLI should feel more like a terminal
application while still running fully inside Terminal.

Recommended direction:

- Add a top-level menu when running `listkit` with no arguments:
  - Create List
  - Manage Templates
  - Config
  - Help
  - Quit
- Give each screen a consistent shape:
  - title
  - short status/context line
  - body/menu
  - footer with controls, such as `[↑↓ select | Enter confirm | Esc back | Ctrl-C quit]`
- Prefer redrawing screens over leaving every previous prompt in scrollback.
  This is the main shift from “chatty wizard” to “terminal app.”
- Keep questionary for the first pass if it remains adequate.
- Consider a real TUI framework later, such as Textual or a direct
  `prompt_toolkit` application, if questionary becomes too limiting.

Do not start with a full TUI rewrite. First add the main menu and consistent
screen footer once the user flows are stable enough that the layout will not be
rewritten every few commits.

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

Add a reverse flow that starts from an Apple Reminders list and saves it as a
template.

Possible command:

```sh
listkit template-from-list
```

Planned flow:

1. Show available Apple Reminders lists.
2. Let the user select a source list.
3. Read incomplete reminders from that list.
4. Ask for a template name and optional short name.
5. Save a new template file.

Initial scope should stay conservative:

- Ignore completed reminders by default.
- Flatten sections unless preserving sections becomes clearly necessary.
- Omit notes, URLs, due dates, tags, and priorities in the first version.
- If a template name already exists, prompt to replace, rename, or cancel.

This becomes more natural after moving to the generic template/item schema.

### Reminders List Identity and Recovery

Keep using Reminders list IDs as the durable target identity, with list names as
cached display text.

Expected behavior:

- When `listkit config` loads the default Reminders list setting, validate the
  stored list ID against current Reminders lists.
- If the ID exists but the name changed, silently update the cached name.
- If the ID is missing, fall back to matching the stored name.
- If the name has one match, save that new ID.
- If the name has multiple matches or no matches, prompt the user to choose or
  create a list.
- During normal `listkit` runs, still show the target list picker before sending so
  stale config can be corrected before writing anything.

For a user with no Reminders lists, prompt rather than assuming:

- create a list using the template name
- enter a different list name
- cancel

Do not default to the short name for new list creation. Short names are intended
as compact tags and may not be user-facing enough.

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
- Moving Apple Reminders settings into a broader multi-target app structure.
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

A future `Restore from Backup` config menu item can restore app-owned files.
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
