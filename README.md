# Easy Reminder Templates

> Alpha software: this project is actively changing and should be used at your
> own risk while it is in development. It can create real Apple Reminders items,
> so consider testing with a throwaway Reminders list first.

Easy Reminder Templates is a local command-line tool for creating Apple
Reminders lists from reusable JSON templates. It can handle recipe ingredient
lists, packing checklists, recurring store purchases, chores, trip prep, or
project checklists.

## Install

Easy Reminder Templates is currently macOS-only.

### 1. Check for Homebrew

```sh
brew --version
```

If that command fails, install Homebrew from:

```text
https://brew.sh
```

### 2. Install pipx

```sh
brew install pipx
pipx ensurepath
```

Close and reopen Terminal if `pipx ensurepath` says your PATH changed.

Check that `pipx` is available:

```sh
pipx --version
```

On older Macs, Homebrew may need to build Python from source. If that is slow or
fails, install Python 3.11 first and tell `pipx` to use it:

```sh
brew install python@3.11
pipx install --python /usr/local/bin/python3.11 git+https://github.com/baconandgames/easy-reminders-templates.git
```

### 3. Install Easy Reminder Templates

```sh
pipx install git+https://github.com/baconandgames/easy-reminders-templates.git
```

Check that `listkit` is available:

```sh
listkit --help
```

To update an existing install:

```sh
pipx upgrade easy-reminder-templates
listkit --version
```

You can also check for updates from the config menu:

```sh
listkit config
```

The update checker uses GitHub Releases. If a newer release exists, `listkit`
shows its changelog before offering the manual update command. You can also skip
that release; a later release will appear again.

For maintainers: the GitHub Release tag and the package version in
`pyproject.toml` must match for `pipx upgrade` to install the expected version.

## First Run

Open the config menu first:

```sh
listkit config
```

Then create a list from a template:

```sh
listkit
```

The first time `listkit` creates Apple Reminders, macOS may ask for permission to
access Reminders.

## Local Development

For local development, install in editable mode:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Usage

Run with an optional template short name:

```sh
listkit
listkit chili
```

When no short name is provided, `listkit` lists available templates and prompts for
a selection.

When installed outside this repository, `listkit` creates user files in:

```text
~/Library/Application Support/Easy Reminder Templates/
```

That folder contains `config.json` and a `templates/` folder.

The CLI then prompts for:

- batch size, when the template includes quantities
- whether to include items marked as usually on hand, when relevant

Interactive prompts can be exited with `Esc`. Pressing `Esc` backs out of
submenus and exits when you reach the top level.

Before sending anything to Apple Reminders, `listkit` shows all template items in a
checkbox list. Items are preselected based on the on-hand prompt, and can be
added or removed before the final list is created.

## Templates

Templates live as individual JSON files under `templates/`.

```text
templates/
  recipes/
    classic-chili.json
  lists/
    beach-day.json
    trader-joes-common-purchases.json
```

See [TEMPLATES.md](TEMPLATES.md) for the full JSON template guide, including
examples, field descriptions, blank-value behavior, and how to create a template
from an existing Apple Reminders list.

Bundled examples show three common use cases:

- `Classic Chili` (`listkit chili`): a recipe with batch scaling and optional
  on-hand ingredients.
- `Beach Day` (`listkit beach`): a reusable packing checklist.
- `Trader Joe's Common Purchases` (`listkit tjs`): a store-specific staples list
  where usually-bought items start selected and occasional purchases are marked
  as on-hand.

## Configuration

Terminal display options live in `config.json` and can be edited directly in a
text editor.

```json
{
  "apple_reminders_list_id": "",
  "apple_reminders_list_name": "Groceries",
  "hidden_apple_reminders_list_ids": [],
  "append_short_name": true,
  "include_on_hand_default": false,
  "standard_text_color": "#f2f0ea",
  "quantity_color": "#37b7f0",
  "selection_color": "#ff4b1f",
  "omitted_ingredient_color": "#777777",
  "skipped_update_version": ""
}
```

Supported color values:

- Hex colors in `#rrggbb` format, when supported by your terminal.
- `black`
- `red`
- `green`
- `yellow`
- `blue`
- `magenta`
- `cyan`
- `white`
- `grey`

Invalid color values fall back to the default for that setting.

Apple Reminders lists can be targeted by `apple_reminders_list_name`, including
lists inside Reminders folders. `listkit` prompts you to choose from available
lists, starts on the configured list name, and shows a few existing items only
when multiple lists share the same name.

At the reminder-list prompt, choose `[ + Create New List]` to create a new Apple
Reminders list before adding the selected template items.

When `apple_reminders_list_id` is set, it is preferred over
`apple_reminders_list_name`.

Run `listkit config` to choose which Apple Reminders lists appear in the list
picker, edit terminal colors, update common options, and check for GitHub release
updates. Hidden lists are stored in `hidden_apple_reminders_list_ids`.
