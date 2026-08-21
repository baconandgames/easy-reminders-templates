from __future__ import annotations

import subprocess

from src.config import Config
from src.delivery import AppleRemindersTarget, DeliveryError, build_apple_reminders_script, get_delivery_target
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
	assert result.created_items == ["1 Apple"]
	assert result.omitted_items == ["1 tsp Salt"]
	assert result.dry_run is True


def test_apple_reminders_target_runs_script_in_create_mode() -> None:
	calls = []

	def fake_runner(args, check, capture_output, text):
		calls.append(
			{
				"args": args,
				"check": check,
				"capture_output": capture_output,
				"text": text,
			}
		)

	recipe = {
		"name": "Test Recipe",
		"ingredients": [
			{
				"name": "Apple",
				"quantity": 1,
				"always_on_hand": False,
			},
		],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	result = AppleRemindersTarget(runner=fake_runner).create_list(
		shopping_list,
		Config(delivery_mode="create", apple_reminders_list_name="Shared Grocery"),
	)

	assert result.dry_run is False
	assert len(calls) == 1
	assert calls[0]["args"][0:2] == ["osascript", "-e"]
	assert 'set targetList to list "Shared Grocery"' in calls[0]["args"][2]
	assert 'make new reminder at end of reminders of targetList with properties {name:"1 Apple"}' in calls[0]["args"][2]
	assert calls[0]["check"] is True
	assert calls[0]["capture_output"] is True
	assert calls[0]["text"] is True


def test_apple_reminders_target_raises_delivery_error_when_script_fails() -> None:
	def failing_runner(_args, check, capture_output, text):
		raise subprocess.CalledProcessError(1, "osascript", stderr="No list found.")

	recipe = {
		"name": "Test Recipe",
		"ingredients": [],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	try:
		AppleRemindersTarget(runner=failing_runner).create_list(
			shopping_list,
			Config(delivery_mode="create"),
		)
	except DeliveryError as error:
		assert str(error) == "No list found."
	else:
		raise AssertionError("Expected DeliveryError")


def test_build_apple_reminders_script_quotes_names() -> None:
	script = build_apple_reminders_script('Kid "Groceries"', ['1 "quoted" item'])

	assert 'list "Kid \\"Groceries\\""' in script
	assert 'properties {name:"1 \\"quoted\\" item"}' in script
