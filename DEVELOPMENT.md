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
├── recipes.json
├── shop
├── bin/
│   └── reminders-helper.swift
├── recipe_shopper/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── delivery.py
│   ├── formatter.py
│   ├── recipes.py
│   ├── default_recipes.json
│   └── bin/
│       └── reminders-helper.swift
└── tests/
    ├── test_delivery.py
    ├── test_shop.py
    ├── test_config.py
    └── test_formatter.py
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
