from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_TARGET_APPS: set[str] = {"apple_reminders"}
SUPPORTED_DELIVERY_MODES: set[str] = {"dry_run", "create"}


@dataclass(frozen=True)
class Config:
	target_app: str = "apple_reminders"
	delivery_mode: str = "dry_run"
	apple_reminders_list_id: str = ""
	apple_reminders_list_name: str = "Groceries"
	hidden_apple_reminders_list_ids: list[str] = field(default_factory=list)
	append_short_name: bool = True
	include_on_hand_default: bool = False
	standard_text_color: str = "default"
	quantity_color: str = "green"
	omitted_ingredient_color: str = "grey"


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

	target_app: str = _read_target_app(raw_data, "target_app", Config.target_app)
	delivery_mode: str = _read_delivery_mode(raw_data, "delivery_mode", Config.delivery_mode)
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
	omitted_ingredient_color: str = _read_color(
		raw_data,
		"omitted_ingredient_color",
		Config.omitted_ingredient_color,
	)

	return Config(
		target_app=target_app,
		delivery_mode=delivery_mode,
		apple_reminders_list_id=apple_reminders_list_id,
		apple_reminders_list_name=apple_reminders_list_name,
		hidden_apple_reminders_list_ids=hidden_apple_reminders_list_ids,
		append_short_name=append_short_name,
		include_on_hand_default=include_on_hand_default,
		standard_text_color=standard_text_color,
		quantity_color=quantity_color,
		omitted_ingredient_color=omitted_ingredient_color,
	)


def save_config(path: Path, config: Config) -> None:
	data: dict[str, Any] = {
		"target_app": config.target_app,
		"delivery_mode": config.delivery_mode,
		"apple_reminders_list_id": config.apple_reminders_list_id,
		"apple_reminders_list_name": config.apple_reminders_list_name,
		"hidden_apple_reminders_list_ids": config.hidden_apple_reminders_list_ids,
		"append_short_name": config.append_short_name,
		"include_on_hand_default": config.include_on_hand_default,
		"standard_text_color": config.standard_text_color,
		"quantity_color": config.quantity_color,
		"omitted_ingredient_color": config.omitted_ingredient_color,
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


def _read_target_app(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: str = _read_string(raw_data, key, default)
	if value not in SUPPORTED_TARGET_APPS:
		raise ConfigLoadError(f'Config value "{key}" has unsupported target "{value}".')

	return value


def _read_delivery_mode(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: str = _read_string(raw_data, key, default)
	if value not in SUPPORTED_DELIVERY_MODES:
		raise ConfigLoadError(f'Config value "{key}" has unsupported mode "{value}".')

	return value


def _read_color(raw_data: dict[str, Any], key: str, default: str) -> str:
	value: Any = raw_data.get(key, default)
	if not isinstance(value, str):
		raise ConfigLoadError(f'Config value "{key}" must be a color name.')

	if value not in {
		"default",
		"black",
		"red",
		"green",
		"yellow",
		"blue",
		"magenta",
		"cyan",
		"white",
		"grey",
	}:
		raise ConfigLoadError(f'Config value "{key}" has unsupported color "{value}".')

	return value
