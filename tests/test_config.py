from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.config import ConfigLoadError, load_config


def test_load_config_uses_defaults_when_file_is_missing() -> None:
	with TemporaryDirectory() as directory:
		config = load_config(Path(directory) / "missing.json")

	assert config.append_short_name is True
	assert config.standard_text_color == "default"
	assert config.quantity_color == "green"
	assert config.omitted_ingredient_color == "grey"


def test_load_config_reads_values() -> None:
	with TemporaryDirectory() as directory:
		path: Path = Path(directory) / "config.json"
		path.write_text(
			'{"append_short_name": false, "standard_text_color": "white", "quantity_color": "cyan", "omitted_ingredient_color": "grey"}',
			encoding="utf-8",
		)

		config = load_config(path)

	assert config.append_short_name is False
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
