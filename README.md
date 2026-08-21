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

### 3. Install Easy Reminder Templates

```sh
pipx install git+https://github.com/baconandgames/easy-reminders-templates.git
```

Check that `shop` is available:

```sh
shop --help
```

## First Run

Open the config menu first:

```sh
shop config
```

Then create a list from a template:

```sh
shop
```

The first time `shop` creates Apple Reminders, macOS may ask for permission to
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
shop
shop chili
```

When no short name is provided, `shop` lists available recipes and prompts for
a selection.

When installed outside this repository, `shop` creates user files in:

```text
~/Library/Application Support/Easy Reminder Templates/
```

That folder contains `config.json` and `recipes.json`.

The CLI then prompts for:

- batch size, defaulting to the template's `default_batch`
- whether to include items marked as usually on hand

Interactive prompts can be cancelled with the `Abort` option, `Ctrl-C`, or `q`
where text input is accepted.

Before sending anything to the target app, `shop` shows all template items in a
checkbox list. Items are preselected based on the on-hand prompt, and can be
added or removed before the final list is created.

## Templates

Templates currently live in `recipes.json`.

```json
{
  "recipes": {
    "<recipe-id>": {
      "name": "Recipe Name",
      "short_name": "Optional tag",
      "default_batch": 1,
      "ingredients": [
        {
          "name": "Ingredient",
          "quantity": 1,
          "unit": "singular unit",
          "always_on_hand": false
        }
      ]
    }
  }
}
```

Notes:

- `short_name` is optional.
- `unit` should be singular, such as `can`, `clove`, or `lb`.
- Omit `unit` when it is not needed.
- `always_on_hand` marks items that are normally already available.
- Quantities are stored numerically and scaled by batch size.

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
  "standard_text_color": "white",
  "quantity_color": "green",
  "omitted_ingredient_color": "grey"
}
```

Supported color values:

- `black`
- `red`
- `green`
- `yellow`
- `blue`
- `magenta`
- `cyan`
- `white`
- `grey`

Invalid config values raise a clear error when `shop` runs.

Supported target app values:

- `apple_reminders`

Apple Reminders lists can be targeted by `apple_reminders_list_name`, including
lists inside Reminders folders. `shop` prompts you to choose from available
lists, starts on the configured list name, and shows a few existing items only
when multiple lists share the same name.

When `apple_reminders_list_id` is set, it is preferred over
`apple_reminders_list_name`.

Run `shop config` to choose which Apple Reminders lists appear in the target
list picker, edit terminal colors, and update common options. Hidden lists are stored in
`hidden_apple_reminders_list_ids`.
