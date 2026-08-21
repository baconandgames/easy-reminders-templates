# Template JSON Guide

> Alpha software: this project is actively changing and should be used at your
> own risk while it is in development. Template fields may still change before a
> stable release.

ListKit templates are plain JSON files. JSON does not allow comments, so use
this file as the reference when creating or editing templates.

## Where Templates Live

Templates live in the `templates/` folder, with one JSON file per template.

```text
templates/
  recipes/
    classic-chili.json
  lists/
    beach-day.json
    trader-joes-common-purchases.json
```

When ListKit is installed outside this repository, user templates live in:

```text
~/Library/Application Support/Easy Reminder Templates/templates/
```

## Template Types

ListKit currently supports two template types:

- `recipe`: a template that usually includes quantities, units, batch scaling,
  and on-hand items.
- `list`: a simpler reusable list, such as packing, travel prep, chores, or
  project setup.

Both types use the same basic JSON structure. A `list` template can still include
quantities later if needed.

The bundled templates show three different use cases:

- `Classic Chili` (`listkit chili`): recipe scaling with quantities, units, and
  optional on-hand ingredients.
- `Beach Day` (`listkit beach`): a reusable packing checklist.
- `Trader Joe's Common Purchases` (`listkit tjs`): a recurring store list where
  frequent purchases start selected and occasional purchases are marked
  `always_on_hand`.

## Minimal Basic List

```json
{
  "schema_version": 1,
  "type": "list",
  "name": "Beach Day",
  "short_name": "beach",
  "items": [
    {
      "name": "Towels"
    },
    {
      "name": "Sunscreen"
    },
    {
      "name": "Water bottles"
    }
  ]
}
```

Run it with:

```sh
listkit beach
```

## Recipe Example

```json
{
  "schema_version": 1,
  "type": "recipe",
  "name": "Classic Chili",
  "short_name": "chili",
  "default_batch": 3,
  "items": [
    {
      "name": "Green bell pepper",
      "quantity": 1,
      "always_on_hand": false
    },
    {
      "name": "Garlic",
      "quantity": 2,
      "unit": "clove",
      "always_on_hand": true
    }
  ]
}
```

## Field Reference

| Field | Required | Applies To | Notes |
| --- | --- | --- | --- |
| `schema_version` | Recommended | Template | Use `1`. Reserved for future migrations. |
| `type` | Yes | Template | Must be `"recipe"` or `"list"`. |
| `name` | Yes | Template | Display name shown in ListKit. |
| `short_name` | No | Template | Optional command shortcut, such as `chili` for `listkit chili`. |
| `default_batch` | No | Template | Positive number used as the default batch size. |
| `items` | Yes | Template | Array of items to add to Reminders. |
| `name` | Yes | Item | Item name shown in ListKit and sent to Reminders. |
| `quantity` | No | Item | Number scaled by batch size when present. |
| `unit` | No | Item | Singular unit name, such as `can`, `clove`, `tbsp`, or `lb`. |
| `always_on_hand` | No | Item | `true` means the item starts unchecked when on-hand items are excluded. Defaults to `false`. Useful for recipe pantry staples, travel items you usually keep packed, or store items you buy only sometimes. |

## Blank Values

ListKit treats these blank string values as intentionally unset:

```json
{
  "default_batch": "",
  "items": [
    {
      "name": "Passport",
      "quantity": "",
      "unit": "",
      "always_on_hand": false
    }
  ]
}
```

This is useful for templates created from Reminders lists. You can leave those
fields blank for a basic list, or fill them in later to turn items into
recipe-style entries.

If an item has a `quantity` but no `unit`, ListKit treats it as a count:

```json
{
  "name": "Apple",
  "quantity": 3,
  "unit": ""
}
```

That renders as `3 Apples`.

## Editing Tips

- JSON strings need double quotes.
- Every item except the last item in an array needs a trailing comma.
- JSON files cannot contain comments.
- Use descriptive filenames, such as `beach-day.json` or `classic-chili.json`.
- Keep item names singular when using quantities without units, where possible.
- Keep unit names singular. ListKit handles simple pluralization in terminal
  output and Reminders item names.

## Creating Templates From Reminders

Run:

```sh
listkit
```

Then choose:

```text
[ + Create Template from List ]
```

ListKit will ask which Apple Reminders list to import, then ask for a template
name and short name. It creates a new file under `templates/lists/`.

Generated templates include blank `default_batch`, `quantity`, and `unit` fields
so they can be edited into recipe-style templates later.

## Future Notes

ListKit may eventually include a full template editor. For now, advanced
template edits happen directly in JSON files.
