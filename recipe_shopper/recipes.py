from __future__ import annotations

import json
from pathlib import Path
from typing import Any


Recipe = dict[str, Any]
RecipeMap = dict[str, Recipe]


class RecipeLoadError(Exception):
	"""Raised when recipes cannot be loaded or validated."""


def load_recipes(path: Path) -> RecipeMap:
	try:
		raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
	except FileNotFoundError as error:
		raise RecipeLoadError(f"Recipe file not found: {path}") from error
	except json.JSONDecodeError as error:
		raise RecipeLoadError(f"Invalid JSON in {path}: {error}") from error

	if not isinstance(raw_data, dict):
		raise RecipeLoadError("Recipe file must contain a JSON object.")

	recipes: Any = raw_data.get("recipes")
	if not isinstance(recipes, dict):
		raise RecipeLoadError('Recipe file must contain a top-level "recipes" object.')

	for recipe_id, recipe in recipes.items():
		_validate_recipe(recipe_id, recipe)

	return recipes


def find_recipe_by_short_name(recipes: RecipeMap, short_name: str) -> tuple[str, Recipe] | None:
	normalized_short_name: str = short_name.casefold()
	matches: list[tuple[str, Recipe]] = []

	for recipe_id, recipe in recipes.items():
		recipe_short_name: Any = recipe.get("short_name")
		if isinstance(recipe_short_name, str) and recipe_short_name.casefold() == normalized_short_name:
			matches.append((recipe_id, recipe))

	if len(matches) > 1:
		raise RecipeLoadError(f'Multiple recipes use short_name "{short_name}".')

	return matches[0] if matches else None


def _validate_recipe(recipe_id: Any, recipe: Any) -> None:
	if not isinstance(recipe_id, str) or recipe_id == "":
		raise RecipeLoadError("Recipe IDs must be non-empty strings.")

	if not isinstance(recipe, dict):
		raise RecipeLoadError(f'Recipe "{recipe_id}" must be an object.')

	if not isinstance(recipe.get("name"), str) or recipe["name"] == "":
		raise RecipeLoadError(f'Recipe "{recipe_id}" must have a non-empty string name.')

	short_name: Any = recipe.get("short_name")
	if short_name is not None and not isinstance(short_name, str):
		raise RecipeLoadError(f'Recipe "{recipe_id}" short_name must be a string when present.')

	default_batch: Any = recipe.get("default_batch")
	if not isinstance(default_batch, int | float) or default_batch <= 0:
		raise RecipeLoadError(f'Recipe "{recipe_id}" must have a positive numeric default_batch.')

	ingredients: Any = recipe.get("ingredients")
	if not isinstance(ingredients, list):
		raise RecipeLoadError(f'Recipe "{recipe_id}" must have an ingredients list.')

	for index, ingredient in enumerate(ingredients, start=1):
		_validate_ingredient(recipe_id, index, ingredient)


def _validate_ingredient(recipe_id: str, index: int, ingredient: Any) -> None:
	label: str = f'Recipe "{recipe_id}" ingredient #{index}'

	if not isinstance(ingredient, dict):
		raise RecipeLoadError(f"{label} must be an object.")

	if not isinstance(ingredient.get("name"), str) or ingredient["name"] == "":
		raise RecipeLoadError(f"{label} must have a non-empty string name.")

	quantity: Any = ingredient.get("quantity")
	if not isinstance(quantity, int | float):
		raise RecipeLoadError(f"{label} must have a numeric quantity.")

	unit: Any = ingredient.get("unit")
	if unit is not None and not isinstance(unit, str):
		raise RecipeLoadError(f"{label} unit must be a string when present.")

	always_on_hand: Any = ingredient.get("always_on_hand")
	if not isinstance(always_on_hand, bool):
		raise RecipeLoadError(f"{label} must have a boolean always_on_hand value.")
