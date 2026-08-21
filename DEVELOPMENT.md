# Recipe Shopper - Development Notes

## Project Goal

Recipe Shopper is a small Python utility that generates Apple Reminders shopping lists from JSON recipe files.

The long-term goal is to make grocery shopping for recurring recipes fast and nearly frictionless while keeping the implementation simple and maintainable.

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
- Standard `venv`
- questionary for terminal prompts
- Git
- Apple Reminders via EventKit
- macOS only

External libraries should stay limited and must clearly improve the project.

---

## Project Structure

```text
recipe-shopper/
├── .gitignore
├── README.md
├── DEVELOPMENT.md
├── config.json
├── recipes.json
├── shop
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── formatter.py
│   └── recipes.py
└── tests/
    ├── test_config.py
    └── test_formatter.py
```

Only create files when they become necessary.

---

## Current Feature Plan

### Phase 1

- Load recipes from JSON.
- List available recipes.
- Select a recipe.
- Ask for batch size, defaulting to `default_batch`.
- Ask whether to include on-hand ingredients.
- Scale ingredient quantities.
- Format ingredient quantities nicely.
- Print the shopping list to the terminal.

### Phase 2

Integrate with Apple Reminders.

The generated reminders should:

- Create a parent reminder for the recipe.
- Create ingredient subtasks.
- Add the recipe URL and notes to the parent reminder.
- Append `[short_name]` to ingredient reminders when configured.
- Target an existing shared Reminders grocery list.
- Print a creation summary, including omitted ingredients in the terminal-only omitted style.

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
