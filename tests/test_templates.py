from __future__ import annotations

from pathlib import Path

import pytest

from listkit.templates import (
	TemplateLoadError,
	find_template_by_short_name,
	load_valid_templates_from_directory,
	load_templates,
	template_uses_batch_size,
)


def test_load_templates_reads_individual_template_files(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	recipes_dir: Path = templates_dir / "recipes"
	lists_dir: Path = templates_dir / "lists"
	recipes_dir.mkdir(parents=True)
	lists_dir.mkdir()
	(recipes_dir / "classic-chili.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "recipe",
  "name": "Classic Chili",
  "short_name": "Chili",
  "default_batch": 3,
  "items": [{"name": "Beans", "quantity": 3}]
}
""",
		encoding="utf-8",
	)
	(lists_dir / "beach-day.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Beach Day",
  "short_name": "Beach",
  "items": [{"name": "Towels"}]
}
""",
		encoding="utf-8",
	)

	templates = load_templates(templates_dir)

	assert sorted(templates) == ["beach-day", "classic-chili"]
	assert templates["classic-chili"]["ingredients"][0]["quantity"] == 3
	assert templates["beach-day"]["ingredients"][0]["name"] == "Towels"
	assert templates["beach-day"]["ingredients"][0]["always_on_hand"] is False


def test_load_templates_disallows_duplicate_filename_stems_across_subfolders(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	recipes_dir: Path = templates_dir / "recipes"
	lists_dir: Path = templates_dir / "lists"
	recipes_dir.mkdir(parents=True)
	lists_dir.mkdir()
	template_json: str = """
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "items": [{"name": "Passport"}]
}
"""
	(recipes_dir / "packing.json").write_text(template_json, encoding="utf-8")
	(lists_dir / "packing.json").write_text(template_json, encoding="utf-8")

	with pytest.raises(TemplateLoadError, match='Duplicate template ID "packing"'):
		load_templates(templates_dir)


def test_load_templates_disallows_duplicate_short_names_case_insensitively(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "Pack",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)
	(templates_dir / "project-setup.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Project Setup",
  "short_name": "pack",
  "items": [{"name": "Create repo"}]
}
""",
		encoding="utf-8",
	)

	with pytest.raises(TemplateLoadError, match='Duplicate short_name "pack"'):
		load_templates(templates_dir)


def test_load_templates_disallows_reserved_short_names(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "settings-list.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Settings List",
  "short_name": "settings",
  "items": [{"name": "Review settings"}]
}
""",
		encoding="utf-8",
	)

	with pytest.raises(TemplateLoadError, match='short_name "settings" is reserved'):
		load_templates(templates_dir)


def test_find_template_by_short_name_matches_template_files(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "Pack",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)

	templates = load_templates(templates_dir)

	assert find_template_by_short_name(templates, "pack") == ("packing", templates["packing"])


def test_template_uses_batch_size_only_when_quantities_exist() -> None:
	assert template_uses_batch_size({"ingredients": [{"name": "Passport", "always_on_hand": False}]}) is False
	assert template_uses_batch_size({"ingredients": [{"name": "Beans", "quantity": 3, "always_on_hand": False}]}) is True


def test_load_templates_treats_blank_recipe_fields_as_unset(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "",
  "default_batch": "",
  "items": [
    {"name": "Passport", "quantity": "", "unit": ""},
    {"name": "Socks", "quantity": 3, "unit": ""}
  ]
}
""",
		encoding="utf-8",
	)

	templates = load_templates(templates_dir)
	template = templates["packing"]

	assert template_uses_batch_size(template) is True
	assert template["default_batch"] is None
	assert template["ingredients"][0]["quantity"] is None
	assert template["ingredients"][0]["unit"] is None
	assert template["ingredients"][0]["always_on_hand"] is False
	assert template["ingredients"][1]["quantity"] == 3
	assert template["ingredients"][1]["unit"] is None


def test_blank_default_batch_and_quantities_do_not_use_batch_size(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "default_batch": "",
  "items": [
    {"name": "Passport", "quantity": "", "unit": ""}
  ]
}
""",
		encoding="utf-8",
	)

	templates = load_templates(templates_dir)

	assert template_uses_batch_size(templates["packing"]) is False


def test_load_templates_allows_blank_item_name_placeholder(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "empty-list.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Empty List",
  "items": [
    {"name": "", "quantity": "", "unit": ""}
  ]
}
""",
		encoding="utf-8",
	)

	templates = load_templates(templates_dir)

	assert templates["empty-list"]["ingredients"][0]["name"] == ""


def test_load_valid_templates_from_directory_skips_invalid_json_and_non_json_files(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "notes.txt").write_text("not a template", encoding="utf-8")
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "pack",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)
	(templates_dir / "broken.json").write_text("{", encoding="utf-8")
	(templates_dir / "invalid-template.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "note",
  "name": "Invalid",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)

	templates, warnings = load_valid_templates_from_directory(templates_dir)

	assert sorted(templates) == ["packing"]
	assert len(warnings) == 2
	assert any("Skipped broken.json" in warning for warning in warnings)
	assert any("Skipped invalid-template.json" in warning for warning in warnings)


def test_load_valid_templates_from_directory_skips_duplicate_ids(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	recipes_dir: Path = templates_dir / "recipes"
	lists_dir: Path = templates_dir / "lists"
	recipes_dir.mkdir(parents=True)
	lists_dir.mkdir()
	(recipes_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "pack",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)
	(lists_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Duplicate Packing",
  "short_name": "duplicate",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)
	templates, warnings = load_valid_templates_from_directory(templates_dir)

	assert sorted(templates) == ["packing"]
	assert len(warnings) == 1
	assert any("duplicate template ID" in warning for warning in warnings)


def test_load_valid_templates_from_directory_skips_duplicate_short_names(tmp_path) -> None:
	templates_dir: Path = tmp_path / "templates"
	templates_dir.mkdir()
	(templates_dir / "packing.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Packing",
  "short_name": "pack",
  "items": [{"name": "Passport"}]
}
""",
		encoding="utf-8",
	)
	(templates_dir / "project.json").write_text(
		"""
{
  "schema_version": 1,
  "type": "list",
  "name": "Project",
  "short_name": "PACK",
  "items": [{"name": "Create repo"}]
}
""",
		encoding="utf-8",
	)

	templates, warnings = load_valid_templates_from_directory(templates_dir)

	assert sorted(templates) == ["packing"]
	assert len(warnings) == 1
	assert any("duplicate short_name" in warning for warning in warnings)
