from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
	included_items: list[ShoppingListItem]
	omitted_items: list[ShoppingListItem]


def build_shopping_list(
	recipe: dict[str, Any],
	batch_size: float,
	include_on_hand: bool,
) -> ShoppingList:
	included_items: list[ShoppingListItem] = []
	omitted_items: list[ShoppingListItem] = []
	short_name: str | None = recipe.get("short_name")

	for ingredient in recipe["ingredients"]:
		item: ShoppingListItem = ShoppingListItem(
			name=ingredient["name"],
			quantity=float(ingredient["quantity"]) * batch_size,
			unit=ingredient.get("unit"),
			tag=short_name,
			omitted=ingredient["always_on_hand"] and not include_on_hand,
		)

		if item.omitted:
			omitted_items.append(item)
		else:
			included_items.append(item)

	return ShoppingList(
		recipe_name=recipe["name"],
		batch_size=batch_size,
		included_items=included_items,
		omitted_items=omitted_items,
	)


def render_shopping_list(shopping_list: ShoppingList) -> str:
	lines: list[str] = [
		f"{shopping_list.recipe_name} ({format_number(shopping_list.batch_size)} {pluralize_phrase('batch', shopping_list.batch_size)})",
		"",
	]

	for item in shopping_list.included_items:
		lines.append(f"- {format_item(item)}")

	return "\n".join(lines)


def format_item(item: ShoppingListItem) -> str:
	tag: str = f" [{item.tag}]" if item.tag is not None else ""

	if item.unit is None:
		return f"{format_number(item.quantity)} {pluralize_phrase(item.name, item.quantity)}{tag}"

	return f"{format_number(item.quantity)} {pluralize_phrase(item.unit, item.quantity)} {item.name}{tag}"


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
