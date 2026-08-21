# Easy Reminder Templates

> Alpha software: this project is actively changing and should be used at your
> own risk while it is in development. It can create real Apple Reminders items,
> so consider testing with a throwaway Reminders list first.

Easy Reminder Templates is a local command-line tool for creating Apple
Reminders lists from reusable JSON templates. Recipes are the first supported
template type, but the format is intended to work for repeatable lists like
packing lists, trip prep, chores, or project checklists.

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

Before sending anything to the target app, `listkit` shows all template items in a
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
```

Recipe-style template:

```json
{
  "schema_version": 1,
  "type": "recipe",
  "name": "Recipe Name",
  "short_name": "Optional tag",
  "default_batch": 1,
  "items": [
    {
      "name": "Ingredient",
      "quantity": 1,
      "unit": "singular unit",
      "always_on_hand": false
    }
  ]
}
```

Simple list template:

```json
{
  "schema_version": 1,
  "type": "list",
  "name": "Beach Day",
  "short_name": "Beach",
  "items": [
    {
      "name": "Towels"
    },
    {
      "name": "Sunscreen"
    }
  ]
}
```

Notes:

- `short_name` is optional.
- `quantity` is optional.
- `unit` should be singular, such as `can`, `clove`, or `lb`.
- Omit `unit` when it is not needed or when no quantity is used.
- `always_on_hand` is optional and defaults to `false`.
- Quantities are stored numerically and scaled by batch size when present.

## Configuration

Terminal display options live in `config.json` and can be edited directly in a
text editor.

```json
{
  "target_app": "apple_reminders",
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

Supported target app values:

- `apple_reminders`

Apple Reminders lists can be targeted by `apple_reminders_list_name`, including
lists inside Reminders folders. `listkit` prompts you to choose from available
lists, starts on the configured list name, and shows a few existing items only
when multiple lists share the same name.

At the reminder-list prompt, choose `[ + Create New List]` to create a new Apple
Reminders list before adding the selected template items.

When `apple_reminders_list_id` is set, it is preferred over
`apple_reminders_list_name`.

Run `listkit config` to choose which Apple Reminders lists appear in the target
list picker, edit terminal colors, update common options, and check for GitHub
release updates. Hidden lists are stored in `hidden_apple_reminders_list_ids`.
