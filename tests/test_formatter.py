from __future__ import annotations

from src.formatter import build_shopping_list, render_shopping_list


def test_build_shopping_list_separates_omitted_items() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{
				"name": "Apple",
				"quantity": 1,
				"always_on_hand": False,
			},
			{
				"name": "Salt",
				"quantity": 1,
				"unit": "tsp",
				"always_on_hand": True,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	assert len(shopping_list.included_items) == 1
	assert len(shopping_list.omitted_items) == 1
	assert shopping_list.included_items[0].name == "Apple"
	assert shopping_list.included_items[0].quantity == 2
	assert shopping_list.omitted_items[0].name == "Salt"


def test_render_shopping_list_includes_scaled_items() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{
				"name": "Apple",
				"quantity": 1,
				"always_on_hand": False,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	assert render_shopping_list(shopping_list, use_color=False) == "Test Recipe (2 batches)\n\n- 2 Apples [Test]"
