from __future__ import annotations

from pathlib import Path

from recipe_shopper.templates import find_template_by_short_name, load_templates, template_uses_batch_size


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

	assert sorted(templates) == ["lists/beach-day", "recipes/classic-chili"]
	assert templates["recipes/classic-chili"]["ingredients"][0]["quantity"] == 3
	assert templates["lists/beach-day"]["ingredients"][0]["name"] == "Towels"
	assert templates["lists/beach-day"]["ingredients"][0]["always_on_hand"] is False


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
