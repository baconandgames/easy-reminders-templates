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
  classic-chili.json
  beach-day.json
  trader-joes-common-purchases.json
```

Subfolders are supported for personal organization, but they do not affect how
templates work. ListKit identifies a template by its filename without `.json`,
so `templates/classic-chili.json` and
`templates/recipes/classic-chili.json` both use the ID `classic-chili`.
Duplicate filenames are not allowed anywhere under `templates/`.

When ListKit is installed outside this repository, user templates live in:

```text
~/Library/Application Support/ListKit/templates/
```

ListKit can also read from one external template folder configured in Settings
under **Manage Sharing (Experimental)**. Shared templates use the same JSON
format and appear with `(shared)` in the template picker.

Use a shared folder for templates that are useful to more than one person, such
as family recipes, packing lists, pet care checklists, recurring store lists, or
household setup lists. Keep templates local when they are private, experimental,
or only useful on your Mac.

For best results, use a dedicated shared folder that contains valid ListKit
template JSON files. Non-JSON files are ignored, so a note or README in the
folder is harmless. Invalid JSON files or JSON files that do not match the
template format are skipped, and ListKit will show a warning while still loading
valid local and shared templates.

Local and shared templates may use the same filename; the shared copy appears as
a separate `(shared)` template. Within each folder, avoid duplicate filenames.
Duplicate short names are allowed, but they are best kept rare. If the same
short name matches more than one template, `listkit <short-name>` will ask which
template to use and show whether each match is local or shared.

When a shared folder is configured, **Create Template from List** asks whether
to save the new template locally or in the shared folder. Choose local while you
are drafting or when the list contains private items. Choose shared when the
template is ready for everyone using that folder. Shared templates are saved
directly in the selected shared folder, not in a generated `lists/` subfolder.

If the shared folder is moved, renamed, or unavailable, ListKit will warn you
and continue with local templates. Use **Help** > **Open Shared Templates
Folder** or **Settings** > **Manage Sharing (Experimental)** to inspect or
change the shared folder.

## Template Types

ListKit currently supports two template types:

- `recipe`: a template that usually includes quantities, units, batch scaling,
  and on-hand items.
- `list`: a simpler reusable list, such as packing, travel prep, chores, or
  project setup.

Both types use the same basic JSON structure. A `list` template can still include
quantities later if needed.

The practical difference is whether the template should ask for a batch size:

- Leave `default_batch` blank or omit it for normal checklists, packing lists,
  store lists, and other templates where each item should be added once.
- Set `default_batch` to a number for templates that should scale quantities,
  such as recipes. ListKit will show a batch-size prompt and multiply item
  quantities by the chosen batch size.

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
| `short_name` | No | Template | Optional command shortcut, such as `chili` for `listkit chili`. Short names do not have to be unique, but duplicate matches require a picker when running `listkit <short-name>`. Non-empty short names cannot use reserved commands such as `config`, `settings`, `help`, `version`, `q`, `quit`, or `cancel`. |
| `default_batch` | No | Template | Positive number used as the default batch size. Leave blank or omit it to skip the batch-size prompt. |
| `items` | Yes | Template | Array of items to add to Reminders. |
| `name` | Yes | Item | Item name shown in ListKit and sent to Reminders. A blank string is allowed as an editable placeholder, but blank items are ignored when running a template. |
| `quantity` | No | Item | Number scaled by batch size when present. Leave blank or omit it for plain checklist items. |
| `unit` | No | Item | Singular unit name, such as `can`, `clove`, `tbsp`, or `lb`. |
| `always_on_hand` | No | Item | `true` means the item starts unchecked when on-hand items are excluded. Defaults to `false`. Useful for recipe pantry staples, travel items you usually keep packed, or store items you buy only sometimes. |

## Choosing Field Values

Use `default_batch` when a template has quantities that should scale together.
For example, a recipe might default to `3` batches because that is the usual
amount you cook. When you run the template, ListKit asks for the batch size and
starts on that default value.

Leave `default_batch` blank or remove it when the list should not scale. This is
usually right for packing lists, recurring store lists, errands, chores, and
project setup checklists. Without `default_batch`, ListKit skips the batch-size
prompt entirely.

Use `quantity` and `unit` only when the amount matters in the final Reminder.
For basic items like `Towels`, `Passport`, or `Coffee pods`, leave both blank or
omit them. For count-based items like `3 Apples`, set `quantity` and leave
`unit` blank.

Use `always_on_hand` for items that should usually start unchecked. In recipes,
that might mean pantry staples. In packing lists, it might mean items that stay
in a go bag. In store lists, it can mean things you buy sometimes, but not every
visit.

Use `short_name` for templates that should be quick to launch from Terminal,
such as `chili`, `beach`, or `tjs`. Leave it blank or omit it when a template is
rarely used or when a descriptive picker name is clearer than another shortcut
to remember. Shared templates can use short names too; if a shortcut matches
more than one template, ListKit asks which one to run.

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

Blank item names are allowed only as placeholders:

```json
{
  "name": "",
  "quantity": "",
  "unit": "",
  "always_on_hand": false
}
```

This is most useful when creating a shell template from an empty Reminders list.
ListKit ignores blank placeholder items until you give them names. If a template
has no named items, ListKit will return to template selection and ask you to edit
the JSON first.

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
- Avoid duplicate filenames, even when files are in different subfolders.
- Prefer unique `short_name` values for shortcuts you use often; `Chili` and
  `chili` are treated as the same shortcut.
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
Create Template from List
```

ListKit will ask which Apple Reminders list to import. If the list has completed
reminders, ListKit can scan recent completed items and show repeated items as
optional additions before asking for a template name and short name. It creates
a new JSON file under `templates/`.

When the entered short name is already used by another template, ListKit keeps
you on the short-name screen, shows `Short name "..." unavailable.`, and fills in
the next available suggestion so you can accept or edit it before saving.

If an external template folder is configured in **Manage Sharing
(Experimental)**, ListKit will also ask whether to save the new template locally
or in the shared folder.

Generated templates include blank `default_batch`, `quantity`, and `unit` fields
so they can be edited into recipe-style templates later.

After saving, ListKit shows a short summary with the template name, item count,
and JSON path. From there, you can open the JSON file immediately or return to
the main menu.

You can also create a template from an empty Reminders list. This creates a
shell JSON file with one blank item placeholder, which is useful when you want
to start editing a template by hand.

To edit or remove templates from Finder, open `listkit`, choose **Help**, then
choose **Open Templates Folder**. Deleting a template JSON file removes it from
the template picker the next time **Add from Template** opens.

## Future Notes

ListKit may eventually include a full template editor. For now, advanced
template edits happen directly in JSON files.
