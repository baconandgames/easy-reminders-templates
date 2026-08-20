from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

from src.delivery import DeliveryResult


SHOP_PATH: Path = Path(__file__).resolve().parents[1] / "shop"
SHOP_LOADER = SourceFileLoader("shop_script", str(SHOP_PATH))
SHOP_SPEC = importlib.util.spec_from_loader("shop_script", SHOP_LOADER)
assert SHOP_SPEC is not None
assert SHOP_SPEC.loader is not None
shop_script = importlib.util.module_from_spec(SHOP_SPEC)
SHOP_SPEC.loader.exec_module(shop_script)


def test_prompt_for_include_on_hand_uses_false_default() -> None:
	with patch("builtins.input", return_value=""):
		assert shop_script.prompt_for_include_on_hand(default=False) is False


def test_prompt_for_include_on_hand_uses_true_default() -> None:
	with patch("builtins.input", return_value=""):
		assert shop_script.prompt_for_include_on_hand(default=True) is True


def test_render_delivery_result_shows_dry_run_summary() -> None:
	result = DeliveryResult(
		target_app="apple_reminders",
		target_name="Apple Reminders: Groceries",
		created_parent="Classic Chili",
		created_items=["5 lb Ground turkey", "9 cans Beans"],
		omitted_items=["3 tsp Salt"],
		dry_run=True,
	)

	assert shop_script.render_delivery_result(result) == (
		"Dry run: Apple Reminders: Groceries\n"
		"Parent: Classic Chili\n"
		"Included: 2 items\n"
		"Omitted: 1 item"
	)
