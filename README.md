# Recipe Shopper - Codex Project Context

## Project Goal

Recipe Shopper is a small Python utility that generates Apple Reminders shopping lists from JSON recipe files.

The long-term goal is to make grocery shopping for recurring recipes fast and nearly frictionless while keeping the implementation simple and maintainable.

This is a local project stored in Git (local only for now).

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
- Standard `venv`
- Git
- Apple Reminders (EventKit integration later)
- macOS only

No external libraries should be added unless they clearly improve the project.

---

## Planned Project Structure

```
recipe-shopper/
├── .gitignore
├── README.md
├── recipes.json
├── shop.py
└── src/
    ├── __init__.py
    ├── recipes.py
    ├── formatter.py
    ├── reminders.py
    └── ui.py
```

Only create files when they become necessary.

---

## Current JSON Schema

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

### Notes

- `short_name` is optional.
- `unit` is singular (`can`, `clove`, `lb`, etc.).
- Omit `unit` entirely when it is not needed.
- `always_on_hand` indicates ingredients that are normally kept in the pantry.
- Quantities are stored numerically and formatted later.

---

## Current Feature Plan

### Phase 1

- Load recipes from JSON.
- List available recipes.
- Select a recipe.
- Ask for batch size (defaulting to `default_batch`).
- Scale ingredient quantities.
- Format ingredient quantities nicely.
- Print the shopping list to the terminal.

### Phase 2

Integrate with Apple Reminders.

The generated reminders should:

- Create a parent reminder for the recipe.
- Create ingredient subtasks.
- Add the recipe URL and notes to the parent reminder.
- Append `[short_name]` to ingredient reminders when `short_name` exists.
- Target an existing shared Reminders grocery list.

---

## Deferred Features

These have intentionally been postponed.

- Ingredient IDs
- Pantry inventory
- Store departments
- Multiple recipe databases
- Native macOS application
- Cloud synchronization

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

---

## Immediate Next Task

Implement the recipe loader.

It should:

- Load `recipes.json`.
- Validate the top-level structure.
- Return the recipe dictionary.
- Raise clear errors when the file or schema is invalid.

No EventKit or Apple Reminders work should be started until the recipe engine is functioning correctly.