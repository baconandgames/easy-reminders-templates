from __future__ import annotations

from src.formatter import ColorScheme, build_shopping_list, render_shopping_list


PLAIN_COLORS = ColorScheme(
	standard_text_color="default",
	quantity_color="default",
	omitted_ingredient_color="default",
)


def test_build_shopping_list_separates_omitted_items() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{
				"name": "Salt",
				"quantity": 1,
				"unit": "tsp",
				"always_on_hand": True,
			},
			{
				"name": "Apple",
				"quantity": 1,
				"always_on_hand": False,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	assert len(shopping_list.included_items) == 1
	assert len(shopping_list.omitted_items) == 1
	assert len(shopping_list.items) == 2
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

	assert render_shopping_list(shopping_list, color_scheme=PLAIN_COLORS) == "Test Recipe (2 batches)\n\nIncluded\n---------------------\n- 2     Apples [Test]"


def test_build_shopping_list_can_omit_short_name_tag() -> None:
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

	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False, append_short_name=False)

	assert render_shopping_list(shopping_list, color_scheme=PLAIN_COLORS) == "Test Recipe (2 batches)\n\nIncluded\n--------------\n- 2     Apples"


def test_build_shopping_list_omits_empty_short_name_tag() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "",
		"ingredients": [
			{
				"name": "Apple",
				"quantity": 1,
				"always_on_hand": False,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	assert render_shopping_list(shopping_list, color_scheme=PLAIN_COLORS) == "Test Recipe (2 batches)\n\nIncluded\n--------------\n- 2     Apples"


def test_render_shopping_list_can_include_omitted_items_inline() -> None:
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

	assert render_shopping_list(shopping_list, color_scheme=PLAIN_COLORS, include_omitted=True) == (
		"Test Recipe (2 batches)\n\n"
		"Included\n-------------------------\n"
		"- 2         Apples [Test]\n\n"
		"Omitted\n-------------------------\n"
		"x 2 tsp     Salt [Test]"
	)


def test_render_shopping_list_aligns_ingredient_names() -> None:
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
				"quantity": 1.5,
				"unit": "tsp",
				"always_on_hand": False,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	assert render_shopping_list(shopping_list, color_scheme=PLAIN_COLORS) == (
		"Test Recipe (1 batch)\n\n"
		"Included\n--------------------------\n"
		"- 1           Apple [Test]\n"
		"- 1.5 tsp     Salt [Test]"
	)


def test_render_shopping_list_colors_quantity_and_unit_together() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{
				"name": "Salt",
				"quantity": 1.5,
				"unit": "tsp",
				"always_on_hand": False,
			},
		],
	}

	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	assert render_shopping_list(shopping_list) == "Test Recipe (1 batch)\n\nIncluded\n-------------------------\n- \033[32m1.5 tsp\033[0m     Salt [Test]"
