from __future__ import annotations

import json
import subprocess

from recipe_shopper.config import Config
from recipe_shopper.delivery import AppleRemindersTarget, DeliveryError, DeliveryTargetOption, get_delivery_target
from recipe_shopper.formatter import build_shopping_list


def test_get_delivery_target_returns_apple_reminders_target() -> None:
	target = get_delivery_target("apple_reminders")

	assert isinstance(target, AppleRemindersTarget)


def test_apple_reminders_target_runs_script() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append(
			{
				"args": args,
				"input": input,
				"check": check,
				"capture_output": capture_output,
				"text": text,
			}
		)
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{
							"id": "list-1",
							"name": "Shared Grocery",
							"source": "iCloud",
							"item_count": 1,
							"sample_items": ["Milk"],
						}
					]
				),
				stderr="",
			)
		return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

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
		Config(apple_reminders_list_name="Shared Grocery"),
	)

	assert result.target_app == "apple_reminders"
	assert result.target_name == "Apple Reminders: Shared Grocery"
	assert result.created_items == ["1 Apple"]
	assert len(calls) == 2
	assert calls[0]["args"][2] == "list-targets"
	assert calls[1]["args"][0] == "swift"
	assert calls[1]["args"][2] == "create-reminders"
	assert json.loads(calls[1]["input"]) == {
		"listIdentifier": "list-1",
		"listName": "Shared Grocery",
		"items": ["1 Apple"],
	}
	assert calls[1]["check"] is True
	assert calls[1]["capture_output"] is True
	assert calls[1]["text"] is True


def test_apple_reminders_target_uses_configured_list_id_after_listing_targets() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append(
			{
				"args": args,
				"input": input,
				"check": check,
				"capture_output": capture_output,
				"text": text,
			}
		)
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{
							"id": "list-1",
							"name": "Shared Grocery",
							"source": "iCloud",
							"item_count": 1,
							"sample_items": ["Milk"],
						}
					]
				),
				stderr="",
			)
		return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

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

	AppleRemindersTarget(runner=fake_runner).create_list(
		shopping_list,
		Config(
			apple_reminders_list_id="list-1",
			apple_reminders_list_name="Shared Grocery",
		),
	)

	assert len(calls) == 2
	assert calls[0]["args"][2] == "list-targets"
	assert calls[1]["args"][2] == "create-reminders"
	assert json.loads(calls[1]["input"])["listIdentifier"] == "list-1"


def test_apple_reminders_target_uses_selector_for_duplicate_list_names() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append({"args": args, "input": input})
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{"id": "list-1", "name": "Test", "source": "iCloud", "item_count": 1, "sample_items": ["Bacon"]},
						{"id": "list-2", "name": "Test", "source": "iCloud", "item_count": 0, "sample_items": []},
						{"id": "list-3", "name": "Test", "source": "Local", "item_count": 1, "sample_items": ["TP"]},
					]
				),
				stderr="",
			)
		return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

	def selector(target_name: str, options: list[DeliveryTargetOption], omitted_count: int) -> DeliveryTargetOption:
		assert target_name == "Test"
		assert len(options) == 3
		assert omitted_count == 0
		return options[2]

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

	AppleRemindersTarget(runner=fake_runner, target_selector=selector).create_list(
		shopping_list,
		Config(apple_reminders_list_name="Test"),
	)

	assert json.loads(calls[1]["input"])["listIdentifier"] == "list-3"


def test_apple_reminders_target_sends_selected_list_name_to_helper() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append({"args": args, "input": input})
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{"id": "list-1", "name": "Test", "source": "iCloud", "item_count": 0, "sample_items": []},
					]
				),
				stderr="",
			)
		return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

	def selector(_target_name: str, options: list[DeliveryTargetOption], _omitted_count: int) -> DeliveryTargetOption:
		return options[0]

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

	AppleRemindersTarget(runner=fake_runner, target_selector=selector).create_list(
		shopping_list,
		Config(apple_reminders_list_name="Groceries"),
	)

	assert json.loads(calls[1]["input"])["listName"] == "Test"


def test_apple_reminders_target_hides_configured_list_ids_from_selector() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append({"args": args, "input": input})
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{"id": "list-1", "name": "Test", "source": "iCloud", "item_count": 1, "sample_items": ["Bacon"]},
						{"id": "list-2", "name": "Archive", "source": "iCloud", "item_count": 0, "sample_items": []},
					]
				),
				stderr="",
			)
		return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

	def selector(target_name: str, options: list[DeliveryTargetOption], omitted_count: int) -> DeliveryTargetOption:
		assert target_name == "Test"
		assert [option.name for option in options] == ["Test"]
		assert omitted_count == 1
		return options[0]

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

	AppleRemindersTarget(runner=fake_runner, target_selector=selector).create_list(
		shopping_list,
		Config(
			apple_reminders_list_name="Test",
			hidden_apple_reminders_list_ids=["list-2"],
		),
	)

	assert json.loads(calls[1]["input"])["listIdentifier"] == "list-1"


def test_apple_reminders_target_raises_when_duplicate_names_have_no_selector() -> None:
	def fake_runner(args, input, check, capture_output, text):
		return subprocess.CompletedProcess(
			args,
			0,
			stdout=json.dumps(
				[
					{"id": "list-1", "name": "Test", "source": "iCloud", "item_count": 0, "sample_items": []},
					{"id": "list-2", "name": "Test", "source": "iCloud", "item_count": 0, "sample_items": []},
				]
			),
			stderr="",
		)

	recipe = {
		"name": "Test Recipe",
		"ingredients": [],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	try:
		AppleRemindersTarget(runner=fake_runner).create_list(
			shopping_list,
			Config(apple_reminders_list_name="Test"),
		)
	except DeliveryError as error:
		assert str(error) == 'Multiple reminder lists named "Test" were found.'
	else:
		raise AssertionError("Expected DeliveryError")


def test_apple_reminders_target_raises_delivery_error_when_script_fails() -> None:
	def failing_runner(_args, input, check, capture_output, text):
		raise subprocess.CalledProcessError(1, "swift", stderr="No list found.")

	recipe = {
		"name": "Test Recipe",
		"ingredients": [],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	try:
		AppleRemindersTarget(runner=failing_runner).create_list(
			shopping_list,
			Config(),
		)
	except DeliveryError as error:
		assert str(error) == "No list found."
	else:
		raise AssertionError("Expected DeliveryError")
