# Recipe Shopper

Recipe Shopper is a local command-line tool for generating shopping lists from
JSON recipe files.

## Usage

Create a virtual environment and install dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run with an optional recipe short name:

```sh
shop
shop chili
```

When no short name is provided, `shop` lists available recipes and prompts for
a selection.

The CLI then prompts for:

- batch size, defaulting to the recipe's `default_batch`
- whether to include ingredients marked as usually on hand

Interactive prompts can be cancelled with the `Abort` option, `Ctrl-C`, or `q`
where text input is accepted.

Before sending anything to the target app, `shop` shows all ingredients in a
checkbox list. Ingredients are preselected based on the on-hand prompt, and can
be added or removed before the final ingredient list is created.

## Recipes

Recipes live in `recipes.json`.

```json
{
  "recipes": {
    "<recipe-id>": {
      "name": "Recipe Name",
      "short_name": "Optional tag",
      "url": "Optional URL",
      "notes": "Optional notes",
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
- `always_on_hand` marks ingredients that are normally kept in the pantry.
- Quantities are stored numerically and scaled by batch size.

## Configuration

Terminal display options live in `config.json` and can be edited directly in a
text editor.

```json
{
  "target_app": "apple_reminders",
  "delivery_mode": "dry_run",
  "apple_reminders_list_id": "",
  "apple_reminders_list_name": "Groceries",
  "hidden_apple_reminders_list_ids": [],
  "append_short_name": true,
  "include_on_hand_default": false,
  "standard_text_color": "default",
  "quantity_color": "green",
  "omitted_ingredient_color": "grey"
}
```

Supported color values:

- `default`
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

Supported delivery modes:

- `dry_run`: print what would be created without changing the target app
- `create`: create reminders in the configured Apple Reminders list

Apple Reminders lists can be targeted by `apple_reminders_list_name`, including
lists inside Reminders folders. `shop` prompts you to choose from available
lists, starts on the configured list name, and shows a few existing items only
when multiple lists share the same name.

When `apple_reminders_list_id` is set, it is preferred over
`apple_reminders_list_name`.

Run `shop config` to choose which Apple Reminders lists appear in the target
list picker. Hidden lists are stored in `hidden_apple_reminders_list_ids`.
