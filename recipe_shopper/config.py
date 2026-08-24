from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from recipe_shopper.colors import normalize_color


UsageRecord = dict[str, str | int]
UsageCounts = dict[str, UsageRecord]


DEFAULT_STANDARD_TEXT_COLOR: str = "#f2f0ea"
DEFAULT_QUANTITY_COLOR: str = "#37b7f0"
DEFAULT_SELECTION_COLOR: str = "#ff4b1f"
DEFAULT_OMITTED_INGREDIENT_COLOR: str = "#777777"
TEMPLATE_SORT_ORDER_OPTIONS: set[str] = {
	"name_asc",
	"name_desc",
	"most_frequently_used",
}
REMINDERS_LIST_SORT_ORDER_OPTIONS: set[str] = {
	"name_asc",
	"name_desc",
	"most_frequently_used",
	"item_count_asc",
	"item_count_desc",
}


@dataclass(frozen=True)
class Config:
	apple_reminders_list_id: str = ""
	apple_reminders_list_name: str = "Groceries"
	hidden_apple_reminders_list_ids: list[str] = field(default_factory=list)
	append_short_name: bool = True
	include_on_hand_default: bool = False
	standard_text_color: str = DEFAULT_STANDARD_TEXT_COLOR
	quantity_color: str = DEFAULT_QUANTITY_COLOR
	selection_color: str = DEFAULT_SELECTION_COLOR
	omitted_ingredient_color: str = DEFAULT_OMITTED_INGREDIENT_COLOR
	skipped_update_version: str = ""
	template_sort_order: str = "name_asc"
	reminders_list_sort_order: str = "name_asc"
	template_usage_counts: UsageCounts = field(default_factory=dict)
	reminders_list_usage_counts: UsageCounts = field(default_factory=dict)
	external_templates_path: str = ""


class ConfigLoadError(Exception):
	"""Raised when config cannot be loaded or validated."""


def load_config(path: Path) -> Config:
	if not path.exists():
		return Config()

	try:
		raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
	except json.JSONDecodeError as error:
		raise ConfigLoadError(f"Invalid JSON in {path}: {error}") from error

	if not isinstance(raw_data, dict):
		raise ConfigLoadError("Config file must contain a JSON object.")

	apple_reminders_list_id: str = _read_optional_string(
		raw_data,
		"apple_reminders_list_id",
		Config.apple_reminders_list_id,
	)
	apple_reminders_list_name: str = _read_string(
		raw_data,
		"apple_reminders_list_name",
		Config.apple_reminders_list_name,
	)
	hidden_apple_reminders_list_ids: list[str] = _read_string_list(
		raw_data,
		"hidden_apple_reminders_list_ids",
		[],
	)
	append_short_name: bool = _read_bool(raw_data, "append_short_name", Config.append_short_name)
	include_on_hand_default: bool = _read_bool(raw_data, "include_on_hand_default", Config.include_on_hand_default)
	standard_text_color: str = _read_color(raw_data, "standard_text_color", Config.standard_text_color)
	quantity_color: str = _read_color(raw_data, "quantity_color", Config.quantity_color)
	selection_color: str = _read_color(raw_data, "selection_color", Config.selection_color)
	omitted_ingredient_color: str = _read_color(
		raw_data,
		"omitted_ingredient_color",
		Config.omitted_ingredient_color,
	)
	skipped_update_version: str = _read_optional_string(
		raw_data,
		"skipped_update_version",
		Config.skipped_update_version,
	)
	template_sort_order: str = _read_sort_order(
		raw_data,
		"template_sort_order",
		Config.template_sort_order,
		TEMPLATE_SORT_ORDER_OPTIONS,
	)
	reminders_list_sort_order: str = _read_sort_order(
		raw_data,
		"reminders_list_sort_order",
		Config.reminders_list_sort_order,
		REMINDERS_LIST_SORT_ORDER_OPTIONS,
	)
	template_usage_counts: UsageCounts = _read_usage_counts(raw_data, "template_usage_counts")
	reminders_list_usage_counts: UsageCounts = _read_usage_counts(raw_data, "reminders_list_usage_counts")
	external_templates_path: str = _read_optional_string(
		raw_data,
		"external_templates_path",
		Config.external_templates_path,
	)

	return Config(
		apple_reminders_list_id=apple_reminders_list_id,
		apple_reminders_list_name=apple_reminders_list_name,
		hidden_apple_reminders_list_ids=hidden_apple_reminders_list_ids,
		append_short_name=append_short_name,
		include_on_hand_default=include_on_hand_default,
		standard_text_color=standard_text_color,
		quantity_color=quantity_color,
		selection_color=selection_color,
		omitted_ingredient_color=omitted_ingredient_color,
		skipped_update_version=skipped_update_version,
		template_sort_order=template_sort_order,
		reminders_list_sort_order=reminders_list_sort_order,
		template_usage_counts=template_usage_counts,
		reminders_list_usage_counts=reminders_list_usage_counts,
		external_templates_path=external_templates_path,
	)


def save_config(path: Path, config: Config) -> None:
	data: dict[str, Any] = {
		"apple_reminders_list_id": config.apple_reminders_list_id,
		"apple_reminders_list_name": config.apple_reminders_list_name,
		"hidden_apple_reminders_list_ids": config.hidden_apple_reminders_list_ids,
		"append_short_name": config.append_short_name,
		"include_on_hand_default": config.include_on_hand_default,
		"standard_text_color": config.standard_text_color,
		"quantity_color": config.quantity_color,
		"selection_color": config.selection_color,
		"omitted_ingredient_color": config.omitted_ingredient_color,
		"skipped_update_version": config.skipped_update_version,
		"template_sort_order": config.template_sort_order,
		"reminders_list_sort_order": config.reminders_list_sort_order,
		"template_usage_counts": config.template_usage_counts,
		"reminders_list_usage_counts": config.reminders_list_usage_counts,
		"external_templates_path": config.external_templates_path,
	}
	path.write_text(f"{json.dumps(data, indent=2)}\n", encoding="utf-8")


def _read_bool(raw_data: dict[str, Any], key: str, default: bool) -> bool:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, bool):
		raise ConfigLoadError(f'Config value "{key}" must be true or false.')

	return value


def _read_string(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, str):
		raise ConfigLoadError(f'Config value "{key}" must be a string.')

	if value.strip() == "":
		raise ConfigLoadError(f'Config value "{key}" must not be empty.')

	return value


def _read_optional_string(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, str):
		raise ConfigLoadError(f'Config value "{key}" must be a string.')

	return value


def _read_string_list(raw_data: dict[str, Any], key: str, default: list[str]) -> list[str]:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, list):
		raise ConfigLoadError(f'Config value "{key}" must be an array of strings.')

	for item in value:
		if not isinstance(item, str):
			raise ConfigLoadError(f'Config value "{key}" must be an array of strings.')

	return value


def _read_color(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, str):
		raise ConfigLoadError(f'Config value "{key}" must be a color name or hex color.')

	return normalize_color(value, default)


def _read_sort_order(raw_data: dict[str, Any], key: str, default: str, valid_options: set[str]) -> str:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, str) or value not in valid_options:
		valid_values = ", ".join(sorted(valid_options))
		raise ConfigLoadError(f'Config value "{key}" must be one of: {valid_values}.')

	return value


def _read_usage_counts(raw_data: dict[str, Any], key: str) -> UsageCounts:
	value: Any = raw_data.get(key, {})
	if not isinstance(value, dict):
		raise ConfigLoadError(f'Config value "{key}" must be an object of usage records.')

	counts: UsageCounts = {}
	for count_key, record in value.items():
		if not isinstance(count_key, str):
			raise ConfigLoadError(f'Config value "{key}" must be an object of usage records.')
		if isinstance(record, int) and record >= 0:
			counts[count_key] = {"name": "", "count": record}
			continue
		if not isinstance(record, dict):
			raise ConfigLoadError(f'Config value "{key}" must be an object of usage records.')
		name: Any = record.get("name", "")
		count: Any = record.get("count")
		if not isinstance(name, str) or not isinstance(count, int) or count < 0:
			raise ConfigLoadError(f'Config value "{key}" must use records with string name and non-negative integer count.')
		counts[count_key] = {"name": name, "count": count}

	return counts
