from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config import Config, ConfigLoadError, load_config, save_config


def test_load_config_uses_defaults_when_file_is_missing() -> None:
	with TemporaryDirectory() as directory:
		config = load_config(Path(directory) / "missing.json")

	assert config.target_app == "apple_reminders"
	assert config.delivery_mode == "dry_run"
	assert config.apple_reminders_list_id == ""
	assert config.apple_reminders_list_name == "Groceries"
	assert config.hidden_apple_reminders_list_ids == []
	assert config.append_short_name is True
	assert config.include_on_hand_default is False
	assert config.standard_text_color == "default"
	assert config.quantity_color == "green"
	assert config.omitted_ingredient_color == "grey"


def test_load_config_reads_values() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text(
			'{"target_app": "apple_reminders", "delivery_mode": "create", "apple_reminders_list_id": "abc123", "apple_reminders_list_name": "Shared Grocery", "hidden_apple_reminders_list_ids": ["list-1", "list-2"], "append_short_name": false, "include_on_hand_default": true, "standard_text_color": "white", "quantity_color": "cyan", "omitted_ingredient_color": "grey"}',
			encoding="utf-8",
		)

		config = load_config(path)

	assert config.target_app == "apple_reminders"
	assert config.delivery_mode == "create"
	assert config.apple_reminders_list_id == "abc123"
	assert config.apple_reminders_list_name == "Shared Grocery"
	assert config.hidden_apple_reminders_list_ids == ["list-1", "list-2"]
	assert config.append_short_name is False
	assert config.include_on_hand_default is True
	assert config.standard_text_color == "white"
	assert config.quantity_color == "cyan"
	assert config.omitted_ingredient_color == "grey"


def test_load_config_rejects_invalid_boolean_values() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"append_short_name": "no"}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "append_short_name" must be true or false.' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")


def test_load_config_rejects_invalid_color_values() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"quantity_color": "orange"}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "quantity_color" has unsupported color "orange".' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")


def test_save_config_writes_values() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"

		save_config(
			path,
			Config(
				delivery_mode="create",
				apple_reminders_list_name="Shared Grocery",
				hidden_apple_reminders_list_ids=["list-1"],
			),
		)

		data = json.loads(path.read_text(encoding="utf-8"))

	assert data["delivery_mode"] == "create"
	assert data["apple_reminders_list_name"] == "Shared Grocery"
	assert data["hidden_apple_reminders_list_ids"] == ["list-1"]


def test_load_config_rejects_invalid_hidden_reminders_list_ids() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"hidden_apple_reminders_list_ids": ["list-1", 1]}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "hidden_apple_reminders_list_ids" must be an array of strings.' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")


def test_load_config_rejects_invalid_target_apps() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"target_app": "google_notes"}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "target_app" has unsupported target "google_notes".' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")


def test_load_config_rejects_empty_reminders_list_names() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"apple_reminders_list_name": ""}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "apple_reminders_list_name" must not be empty.' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")


def test_load_config_rejects_invalid_delivery_modes() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text('{"delivery_mode": "send"}', encoding="utf-8")

		try:
			load_config(path)
		except ConfigLoadError as error:
			assert 'Config value "delivery_mode" has unsupported mode "send".' == str(error)
		else:
			raise AssertionError("Expected ConfigLoadError")
