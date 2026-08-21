from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_TARGET_APPS: set[str] = {"apple_reminders"}
SUPPORTED_DELIVERY_MODES: set[str] = {"dry_run", "create"}


@dataclass(frozen=True)
class Config:
	target_app: str = "apple_reminders"
	delivery_mode: str = "dry_run"
	apple_reminders_list_name: str = "Groceries"
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
	apple_reminders_list_name: str = _read_string(
		raw_data,
		"apple_reminders_list_name",
		Config.apple_reminders_list_name,
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
		apple_reminders_list_name=apple_reminders_list_name,
		append_short_name=append_short_name,
		include_on_hand_default=include_on_hand_default,
		standard_text_color=standard_text_color,
		quantity_color=quantity_color,
		omitted_ingredient_color=omitted_ingredient_color,
	)


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
