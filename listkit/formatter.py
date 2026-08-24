from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from listkit.colors import terminal_color_code
from listkit.config import (
	DEFAULT_OMITTED_INGREDIENT_COLOR,
	DEFAULT_QUANTITY_COLOR,
	DEFAULT_STANDARD_TEXT_COLOR,
)


RESET: str = "\033[0m"
ITEM_NAME_GAP: int = 5


@dataclass(frozen=True)
class ColorScheme:
	standard_text_color: str = DEFAULT_STANDARD_TEXT_COLOR
	quantity_color: str = DEFAULT_QUANTITY_COLOR
	omitted_ingredient_color: str = DEFAULT_OMITTED_INGREDIENT_COLOR


@dataclass(frozen=True)
class ShoppingListItem:
	name: str
	quantity: float | None
	unit: str | None
	tag: str | None
	omitted: bool
	always_on_hand: bool


@dataclass(frozen=True)
class ShoppingList:
	recipe_name: str
	batch_size: float | None
	items: list[ShoppingListItem]
	included_items: list[ShoppingListItem]
	omitted_items: list[ShoppingListItem]


def build_shopping_list(
	recipe: dict[str, Any],
	batch_size: float | None,
	include_on_hand: bool,
	append_short_name: bool = True,
) -> ShoppingList:
	items: list[ShoppingListItem] = []
	included_items: list[ShoppingListItem] = []
	omitted_items: list[ShoppingListItem] = []
	short_name: str | None = recipe.get("short_name") if append_short_name else None
	ingredients: list[dict[str, Any]] = recipe.get("ingredients", recipe.get("items", []))

	for ingredient in ingredients:
		quantity: float | None = None
		if "quantity" in ingredient and ingredient["quantity"] not in (None, ""):
			quantity = float(ingredient["quantity"])
			if batch_size is not None:
				quantity *= batch_size

		item: ShoppingListItem = ShoppingListItem(
			name=ingredient["name"],
			quantity=quantity,
			unit=ingredient.get("unit") or None,
			tag=short_name,
			omitted=ingredient["always_on_hand"] and not include_on_hand,
			always_on_hand=ingredient["always_on_hand"],
		)
		items.append(item)

		if item.omitted:
			omitted_items.append(item)
		else:
			included_items.append(item)

	return ShoppingList(
		recipe_name=recipe["name"],
		batch_size=batch_size,
		items=items,
		included_items=included_items,
		omitted_items=omitted_items,
	)


def render_shopping_list(
	shopping_list: ShoppingList,
	color_scheme: ColorScheme | None = None,
	include_omitted: bool = False,
) -> str:
	colors: ColorScheme = color_scheme or ColorScheme()
	items: list[ShoppingListItem] = shopping_list.included_items
	if include_omitted:
		items = shopping_list.included_items + shopping_list.omitted_items
	prefix_width: int = max((len(format_item_prefix(item)) for item in items), default=0)
	line_width: int = calculate_line_width(items, prefix_width)
	lines: list[str] = [
		style_text(
			format_shopping_list_title(shopping_list),
			colors.standard_text_color,
		),
		"",
		style_text("Included", colors.standard_text_color),
		style_text("-" * line_width, colors.standard_text_color),
	]

	for item in shopping_list.included_items:
		lines.append(style_text(f"- {format_item(item, prefix_width, colors)}", colors.standard_text_color))

	if not include_omitted:
		return "\n".join(lines)

	lines.append("")
	lines.append(style_text("Omitted", colors.omitted_ingredient_color))
	lines.append(style_text("-" * line_width, colors.omitted_ingredient_color))
	for item in shopping_list.omitted_items:
		lines.append(style_text(f"x {format_item(item, prefix_width, None)}", colors.omitted_ingredient_color))

	return "\n".join(lines)


def calculate_line_width(items: list[ShoppingListItem], prefix_width: int) -> int:
	item_width: int = max((len(format_item_name(item)) + len(format_item_tag(item)) for item in items), default=0)
	if prefix_width == 0:
		return 2 + item_width

	return 2 + prefix_width + ITEM_NAME_GAP + item_width


def format_shopping_list_title(shopping_list: ShoppingList) -> str:
	if shopping_list.batch_size is None:
		return shopping_list.recipe_name

	return (
		f"{shopping_list.recipe_name} "
		f"({format_number(shopping_list.batch_size)} {pluralize_phrase('batch', shopping_list.batch_size)})"
	)


def format_item(
	item: ShoppingListItem,
	prefix_width: int,
	color_scheme: ColorScheme | None = None,
) -> str:
	tag: str = format_item_tag(item)
	prefix: str = format_item_prefix(item)
	if prefix_width == 0:
		return f"{format_item_name(item)}{tag}"

	padded_prefix: str = prefix.ljust(prefix_width)
	if color_scheme is not None:
		padded_prefix = style_text(padded_prefix, color_scheme.quantity_color)

	return f"{padded_prefix}{' ' * ITEM_NAME_GAP}{format_item_name(item)}{tag}"


def format_item_name(item: ShoppingListItem) -> str:
	if item.quantity is None:
		return item.name

	if item.unit is None:
		return pluralize_phrase(item.name, item.quantity)

	return item.name


def format_item_tag(item: ShoppingListItem) -> str:
	return f" [{item.tag}]" if item.tag else ""


def format_item_prefix(item: ShoppingListItem) -> str:
	if item.quantity is None:
		return ""

	quantity: str = format_number(item.quantity)
	if item.unit is None:
		return quantity

	return f"{quantity} {pluralize_phrase(item.unit, item.quantity)}"


def format_delivery_item(item: ShoppingListItem) -> str:
	prefix: str = format_item_prefix(item)
	if prefix == "":
		return f"{format_item_name(item)}{format_item_tag(item)}"

	return f"{prefix} {format_item_name(item)}{format_item_tag(item)}"


def style_text(value: str, color_name: str) -> str:
	color: str = terminal_color_code(color_name)
	if color == "":
		return value

	return f"{color}{value}{RESET}"


def format_number(value: float) -> str:
	if value.is_integer():
		return str(int(value))

	return f"{value:.2f}".rstrip("0").rstrip(".")


def pluralize_phrase(value: str, quantity: float) -> str:
	if 0 < quantity <= 1:
		return value

	parts: list[str] = value.split(" ")
	parts[-1] = pluralize_word(parts[-1])
	return " ".join(parts)


def pluralize_word(value: str) -> str:
	if value in {"tbsp", "tsp", "lb", "oz"}:
		return value

	if value.endswith("y") and len(value) > 1 and value[-2].lower() not in "aeiou":
		return f"{value[:-1]}ies"

	if value.endswith(("s", "x", "ch", "sh")):
		return f"{value}es"

	return f"{value}s"
