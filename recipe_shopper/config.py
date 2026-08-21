from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from recipe_shopper.colors import normalize_color


DEFAULT_STANDARD_TEXT_COLOR: str = "#f2f0ea"
DEFAULT_QUANTITY_COLOR: str = "#37b7f0"
DEFAULT_SELECTION_COLOR: str = "#ff4b1f"
DEFAULT_OMITTED_INGREDIENT_COLOR: str = "#777777"


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
