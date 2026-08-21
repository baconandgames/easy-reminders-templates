from __future__ import annotations

import json
from pathlib import Path
from typing import Any


Template = dict[str, Any]
TemplateMap = dict[str, Template]
SUPPORTED_TEMPLATE_TYPES: set[str] = {"recipe", "list"}


class TemplateLoadError(Exception):
	"""Raised when templates cannot be loaded or validated."""


def load_templates(path: Path) -> TemplateMap:
	if not path.exists():
		raise TemplateLoadError(f"Template path not found: {path}")

	if path.is_dir():
		return _load_template_directory(path)

	return _load_legacy_template_file(path)


def find_template_by_short_name(templates: TemplateMap, short_name: str) -> tuple[str, Template] | None:
	normalized_short_name: str = short_name.casefold()
	matches: list[tuple[str, Template]] = []

	for template_id, template in templates.items():
		template_short_name: Any = template.get("short_name")
		if isinstance(template_short_name, str) and template_short_name.casefold() == normalized_short_name:
			matches.append((template_id, template))

	if len(matches) > 1:
		raise TemplateLoadError(f'Multiple templates use short_name "{short_name}".')

	return matches[0] if matches else None


def template_uses_batch_size(template: Template) -> bool:
	items: list[dict[str, Any]] = template.get("ingredients", template.get("items", []))
	return template.get("default_batch") is not None or any(item.get("quantity") is not None for item in items)


def template_has_on_hand_items(template: Template) -> bool:
	items: list[dict[str, Any]] = template.get("ingredients", template.get("items", []))
	return any(item.get("always_on_hand", False) for item in items)


def _load_template_directory(path: Path) -> TemplateMap:
	templates: TemplateMap = {}
	for template_path in sorted(path.rglob("*.json")):
		template_id: str = template_path.relative_to(path).with_suffix("").as_posix()
		template: Template = _read_template_file(template_path)
		_validate_template(template_id, template)
		if template_id in templates:
			raise TemplateLoadError(f'Duplicate template ID "{template_id}".')

		templates[template_id] = template

	if len(templates) == 0:
		raise TemplateLoadError(f"No template JSON files found in: {path}")

	return templates


def _load_legacy_template_file(path: Path) -> TemplateMap:
	try:
		raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
	except FileNotFoundError as error:
		raise TemplateLoadError(f"Template file not found: {path}") from error
	except json.JSONDecodeError as error:
		raise TemplateLoadError(f"Invalid JSON in {path}: {error}") from error

	if not isinstance(raw_data, dict):
		raise TemplateLoadError("Template file must contain a JSON object.")

	templates: Any = raw_data.get("templates", raw_data.get("recipes"))
	if not isinstance(templates, dict):
		raise TemplateLoadError('Template file must contain a top-level "templates" object.')

	loaded_templates: TemplateMap = {}
	for template_id, template in templates.items():
		if not isinstance(template, dict):
			raise TemplateLoadError(f'Template "{template_id}" must be an object.')

		normalized_template: Template = _normalize_template(template)
		_validate_template(template_id, normalized_template)
		loaded_templates[template_id] = normalized_template

	return loaded_templates


def _read_template_file(path: Path) -> Template:
	try:
		raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
	except json.JSONDecodeError as error:
		raise TemplateLoadError(f"Invalid JSON in {path}: {error}") from error

	if not isinstance(raw_data, dict):
		raise TemplateLoadError(f"Template file must contain a JSON object: {path}")

	return _normalize_template(raw_data)


def _normalize_template(template: Template) -> Template:
	normalized: Template = dict(template)
	if normalized.get("default_batch") == "":
		normalized["default_batch"] = None

	if "ingredients" not in normalized and "items" in normalized:
		normalized["ingredients"] = [dict(item) if isinstance(item, dict) else item for item in normalized["items"]]
	elif "ingredients" in normalized:
		normalized["ingredients"] = [
			dict(item) if isinstance(item, dict) else item for item in normalized["ingredients"]
		]

	if "type" not in normalized:
		normalized["type"] = "recipe"

	for item in normalized.get("ingredients", []):
		if not isinstance(item, dict):
			continue
		if item.get("quantity") == "":
			item["quantity"] = None
		if item.get("unit") == "":
			item["unit"] = None
		if "always_on_hand" not in item:
			item["always_on_hand"] = False

	return normalized


def _validate_template(template_id: Any, template: Any) -> None:
	if not isinstance(template_id, str) or template_id == "":
		raise TemplateLoadError("Template IDs must be non-empty strings.")

	if not isinstance(template, dict):
		raise TemplateLoadError(f'Template "{template_id}" must be an object.')

	template_type: Any = template.get("type")
	if template_type not in SUPPORTED_TEMPLATE_TYPES:
		raise TemplateLoadError(f'Template "{template_id}" must have type "recipe" or "list".')

	if not isinstance(template.get("name"), str) or template["name"] == "":
		raise TemplateLoadError(f'Template "{template_id}" must have a non-empty string name.')

	short_name: Any = template.get("short_name")
	if short_name is not None and not isinstance(short_name, str):
		raise TemplateLoadError(f'Template "{template_id}" short_name must be a string when present.')

	default_batch: Any = template.get("default_batch")
	if default_batch is not None and (not isinstance(default_batch, int | float) or default_batch <= 0):
		raise TemplateLoadError(f'Template "{template_id}" default_batch must be a positive number when present.')

	ingredients: Any = template.get("ingredients")
	if not isinstance(ingredients, list):
		raise TemplateLoadError(f'Template "{template_id}" must have an items list.')

	for index, ingredient in enumerate(ingredients, start=1):
		_validate_item(template_id, index, ingredient)


def _validate_item(template_id: str, index: int, item: Any) -> None:
	label: str = f'Template "{template_id}" item #{index}'

	if not isinstance(item, dict):
		raise TemplateLoadError(f"{label} must be an object.")

	if not isinstance(item.get("name"), str) or item["name"] == "":
		raise TemplateLoadError(f"{label} must have a non-empty string name.")

	quantity: Any = item.get("quantity")
	if quantity is not None and not isinstance(quantity, int | float):
		raise TemplateLoadError(f"{label} quantity must be numeric when present.")

	unit: Any = item.get("unit")
	if unit is not None and not isinstance(unit, str):
		raise TemplateLoadError(f"{label} unit must be a string when present.")

	always_on_hand: Any = item.get("always_on_hand")
	if not isinstance(always_on_hand, bool):
		raise TemplateLoadError(f"{label} must have a boolean always_on_hand value.")
