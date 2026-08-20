from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RESET: str = "\033[0m"
ITEM_NAME_GAP: int = 5
COLOR_CODES: dict[str, str] = {
	"default": "",
	"black": "\033[30m",
	"red": "\033[31m",
	"green": "\033[32m",
	"yellow": "\033[33m",
	"blue": "\033[34m",
	"magenta": "\033[35m",
	"cyan": "\033[36m",
	"white": "\033[37m",
	"grey": "\033[90m",
}


@dataclass(frozen=True)
class ColorScheme:
	standard_text_color: str = "default"
	quantity_color: str = "green"
	omitted_ingredient_color: str = "grey"


@dataclass(frozen=True)
class ShoppingListItem:
	name: str
	quantity: float
	unit: str | None
	tag: str | None
	omitted: bool


@dataclass(frozen=True)
class ShoppingList:
	recipe_name: str
	batch_size: float
	items: list[ShoppingListItem]
	included_items: list[ShoppingListItem]
	omitted_items: list[ShoppingListItem]


def build_shopping_list(
	recipe: dict[str, Any],
	batch_size: float,
	include_on_hand: bool,
	append_short_name: bool = True,
) -> ShoppingList:
	items: list[ShoppingListItem] = []
	included_items: list[ShoppingListItem] = []
	omitted_items: list[ShoppingListItem] = []
	short_name: str | None = recipe.get("short_name") if append_short_name else None

	for ingredient in recipe["ingredients"]:
		item: ShoppingListItem = ShoppingListItem(
			name=ingredient["name"],
			quantity=float(ingredient["quantity"]) * batch_size,
			unit=ingredient.get("unit"),
			tag=short_name,
			omitted=ingredient["always_on_hand"] and not include_on_hand,
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
	lines: list[str] = [
		style_text(
			f"{shopping_list.recipe_name} ({format_number(shopping_list.batch_size)} {pluralize_phrase('batch', shopping_list.batch_size)})",
			colors.standard_text_color,
		),
		"",
		style_text("Included:", colors.standard_text_color),
	]

	for item in shopping_list.included_items:
		lines.append(style_text(f"- {format_item(item, prefix_width, colors)}", colors.standard_text_color))

	if not include_omitted:
		return "\n".join(lines)

	lines.append("")
	lines.append(style_text("Omitted:", colors.omitted_ingredient_color))
	for item in shopping_list.omitted_items:
		lines.append(style_text(f"x {format_item(item, prefix_width, None)}", colors.omitted_ingredient_color))

	return "\n".join(lines)


def format_item(
	item: ShoppingListItem,
	prefix_width: int,
	color_scheme: ColorScheme | None = None,
) -> str:
	tag: str = f" [{item.tag}]" if item.tag else ""
	prefix: str = format_item_prefix(item)
	padded_prefix: str = prefix.ljust(prefix_width)
	if color_scheme is not None:
		padded_prefix = style_text(padded_prefix, color_scheme.quantity_color)

	name: str = item.name
	if item.unit is None:
		name = pluralize_phrase(item.name, item.quantity)

	return f"{padded_prefix}{' ' * ITEM_NAME_GAP}{name}{tag}"


def format_item_prefix(item: ShoppingListItem) -> str:
	quantity: str = format_number(item.quantity)
	if item.unit is None:
		return quantity

	return f"{quantity} {pluralize_phrase(item.unit, item.quantity)}"


def format_delivery_item(item: ShoppingListItem) -> str:
	tag: str = f" [{item.tag}]" if item.tag else ""
	prefix: str = format_item_prefix(item)

	name: str = item.name
	if item.unit is None:
		name = pluralize_phrase(item.name, item.quantity)

	return f"{prefix} {name}{tag}"


def style_text(value: str, color_name: str) -> str:
	color: str = COLOR_CODES[color_name]
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
