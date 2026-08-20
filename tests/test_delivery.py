from __future__ import annotations

from src.config import Config
from src.delivery import AppleRemindersTarget, get_delivery_target
from src.formatter import build_shopping_list


def test_get_delivery_target_returns_apple_reminders_target() -> None:
	target = get_delivery_target("apple_reminders")

	assert isinstance(target, AppleRemindersTarget)


def test_apple_reminders_target_returns_dry_run_result() -> None:
	recipe = {
		"name": "Test Recipe",
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
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)
	result = AppleRemindersTarget().create_list(
		shopping_list,
		Config(apple_reminders_list_name="Shared Grocery"),
	)

	assert result.target_app == "apple_reminders"
	assert result.target_name == "Apple Reminders: Shared Grocery"
	assert result.created_parent == "Test Recipe"
	assert result.created_items == ["1 Apple"]
	assert result.omitted_items == ["1 tsp Salt"]
	assert result.dry_run is True
