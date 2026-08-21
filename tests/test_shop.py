from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

from src.delivery import DeliveryResult, DeliveryTargetOption
from src.formatter import build_shopping_list


SHOP_PATH: Path = Path(__file__).resolve().parents[1] / "shop"
SHOP_LOADER = SourceFileLoader("shop_script", str(SHOP_PATH))
SHOP_SPEC = importlib.util.spec_from_loader("shop_script", SHOP_LOADER)
assert SHOP_SPEC is not None
assert SHOP_SPEC.loader is not None
shop_script = importlib.util.module_from_spec(SHOP_SPEC)
SHOP_SPEC.loader.exec_module(shop_script)


class FakePrompt:
	def __init__(self, result) -> None:
		self.result = result

	def ask(self):
		return self.result


def test_select_recipe_displays_recipe_names_without_short_names(monkeypatch) -> None:
	recipe = {"name": "Classic Chili", "short_name": "Chili"}
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt(recipe)

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.select_recipe({"chili": recipe}) == recipe
	assert captured["choices"][0].title == "Classic Chili"


def test_prompt_for_include_on_hand_uses_false_default(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(False))

	assert shop_script.prompt_for_include_on_hand(default=False) is False


def test_prompt_for_include_on_hand_uses_true_default(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(True))

	assert shop_script.prompt_for_include_on_hand(default=True) is True


def test_prompt_for_batch_size_returns_questionary_value(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt("1.5"))

	assert shop_script.prompt_for_batch_size({"default_batch": 3}) == 1.5


def test_prompt_for_batch_size_uses_default_on_empty_selection(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt(""))

	assert shop_script.prompt_for_batch_size({"default_batch": 3}) == 3


def test_prompt_for_batch_size_can_abort(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt("q"))

	try:
		shop_script.prompt_for_batch_size({"default_batch": 3})
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_prompt_for_omitted_items_returns_selected_indexes(monkeypatch) -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)
	captured = {}

	def fake_checkbox(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt([0])

	monkeypatch.setattr(shop_script.questionary, "checkbox", fake_checkbox)

	assert shop_script.prompt_for_omitted_items(shopping_list) == [0]
	assert captured["choices"][0].title == "2 tsp     Salt"


def test_include_selected_omitted_items_promotes_selected_items() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
			{"name": "Oil", "quantity": 1, "unit": "tbsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	updated = shop_script.include_selected_omitted_items(shopping_list, [1])

	assert [item.name for item in updated.included_items] == ["Apple", "Oil"]
	assert [item.name for item in updated.omitted_items] == ["Salt"]
	assert updated.included_items[1].omitted is False


def test_without_item_tags_removes_display_tags_without_mutating_source() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	display_list = shop_script.without_item_tags(shopping_list)

	assert display_list.included_items[0].tag is None
	assert display_list.omitted_items[0].tag is None
	assert shopping_list.included_items[0].tag == "Test"


def test_checked_active_checkbox_row_uses_highlighted_style() -> None:
	control = shop_script.questionary.prompts.common.InquirerControl(
		[shop_script.questionary.Choice(title="Salt", value=0)],
		pointer=">",
	)
	control.selected_options = [0]
	control.pointed_at = 0

	tokens = control._get_choice_tokens()

	assert ("class:highlighted", "[x] ") in tokens
	assert ("class:highlighted", "Salt") in tokens
	assert ("class:selected", "Salt") not in tokens


def test_format_added_count_pluralizes_items() -> None:
	assert shop_script.format_added_count(0) == "0 items added"
	assert shop_script.format_added_count(1) == "1 item added"
	assert shop_script.format_added_count(2) == "2 items added"


def test_render_delivery_result_shows_dry_run_summary() -> None:
	result = DeliveryResult(
		target_app="apple_reminders",
		target_name="Apple Reminders: Groceries",
		created_items=["5 lb Ground turkey", "9 cans Beans"],
		omitted_items=["3 tsp Salt"],
		dry_run=True,
	)

	assert shop_script.render_delivery_result(result) == (
		"Dry run: Apple Reminders: Groceries\n"
		"Included: 2 items\n"
		"Omitted: 1 item"
	)


def test_format_delivery_target_option_shows_sample_items() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=6,
		sample_items=["3 28 oz cans Whole tomatoes", "5 lb Ground turkey", "TP"],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (6) - 3 28 oz can..., 5 lb Ground..., TP"


def test_format_delivery_target_option_handles_empty_list() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=0,
		sample_items=[],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (0)"
