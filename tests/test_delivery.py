from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

from listkit.config import Config
from listkit.delivery import (
	AppleRemindersTarget,
	CompletedReminderItem,
	DeliveryError,
	DeliveryTargetOption,
	default_completed_reminder_suggestion_indexes,
	format_completed_reminder_suggestion,
	get_delivery_target,
	suggest_completed_reminder_items,
)
from listkit.formatter import build_shopping_list


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


def test_apple_reminders_target_creates_target() -> None:
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
		return subprocess.CompletedProcess(
			args,
			0,
			stdout=json.dumps(
				{
					"id": "list-2",
					"name": "Beach",
					"source": "iCloud",
					"item_count": 0,
					"sample_items": [],
				}
			),
			stderr="",
		)

	target = AppleRemindersTarget(runner=fake_runner).create_target("Beach")

	assert target.identifier == "list-2"
	assert target.name == "Beach"
	assert calls[0]["args"][2] == "create-list"
	assert calls[0]["input"] == "Beach"


def test_apple_reminders_target_lists_basic_targets_without_item_details() -> None:
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
		return subprocess.CompletedProcess(
			args,
			0,
			stdout=json.dumps(
				[
					{
						"id": "list-1",
						"name": "Packing",
						"source": "iCloud",
						"item_count": -1,
						"sample_items": [],
					}
				]
			),
			stderr="",
		)

	targets = AppleRemindersTarget(runner=fake_runner).list_basic_targets()

	assert targets == [DeliveryTargetOption("list-1", "Packing", "iCloud", -1, [])]
	assert calls[0]["args"][2] == "list-basic-targets"
	assert calls[0]["input"] == ""
	assert calls[0]["check"] is True
	assert calls[0]["capture_output"] is True
	assert calls[0]["text"] is True


def test_apple_reminders_target_lists_items() -> None:
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
		return subprocess.CompletedProcess(args, 0, stdout=json.dumps(["Passport", "Socks"]), stderr="")

	items = AppleRemindersTarget(runner=fake_runner).list_items("list-1")

	assert items == ["Passport", "Socks"]
	assert calls[0]["args"][2] == "list-items"
	assert calls[0]["input"] == "list-1"
	assert calls[0]["check"] is True
	assert calls[0]["capture_output"] is True
	assert calls[0]["text"] is True


def test_apple_reminders_target_lists_completed_items() -> None:
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
		return subprocess.CompletedProcess(
			args,
			0,
			stdout=json.dumps(
				[
					{"title": "Milk", "completion_date": "2026-08-20T10:00:00Z"},
					{"title": "Eggs", "completion_date": None},
				]
			),
			stderr="",
		)

	items = AppleRemindersTarget(runner=fake_runner).list_completed_items("list-1", days=180)

	assert items == [
		CompletedReminderItem(title="Milk", completion_date="2026-08-20T10:00:00Z"),
		CompletedReminderItem(title="Eggs", completion_date=None),
	]
	assert calls[0]["args"][2] == "list-completed-items"
	assert json.loads(calls[0]["input"]) == {"listIdentifier": "list-1", "days": 180}
	assert calls[0]["check"] is True
	assert calls[0]["capture_output"] is True
	assert calls[0]["text"] is True


def test_suggest_completed_reminder_items_ranks_repeated_recent_items() -> None:
	recent_date: str = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
	older_date: str = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
	completed_items = [
		CompletedReminderItem(title="Milk", completion_date=older_date),
		CompletedReminderItem(title=" milk ", completion_date=recent_date),
		CompletedReminderItem(title="Bananas", completion_date=older_date),
		CompletedReminderItem(title="Bananas", completion_date=older_date),
		CompletedReminderItem(title="Eggs", completion_date=recent_date),
		CompletedReminderItem(title="Eggs", completion_date=recent_date),
		CompletedReminderItem(title="Bread", completion_date=recent_date),
	]

	suggestions = suggest_completed_reminder_items(completed_items, existing_items=["milk"])

	assert [suggestion.title for suggestion in suggestions] == ["Eggs", "Bananas"]
	assert suggestions[0].frequency == 2
	assert suggestions[0].recent_count == 2
	assert suggestions[0].score == 4.0
	assert suggestions[1].frequency == 2
	assert suggestions[1].recent_count == 0
	assert suggestions[1].score == 2.0


def test_completed_reminder_suggestion_label_includes_frequency() -> None:
	suggestion = suggest_completed_reminder_items(
		[
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Eggs", completion_date=None),
		],
		existing_items=[],
	)[0]

	assert format_completed_reminder_suggestion(suggestion) == "Eggs (2)"


def test_default_completed_reminder_suggestions_are_checked_on_frequency_curve() -> None:
	suggestions = suggest_completed_reminder_items(
		[
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Eggs", completion_date=None),
			CompletedReminderItem(title="Bread", completion_date=None),
			CompletedReminderItem(title="Bread", completion_date=None),
		],
		existing_items=[],
	)

	assert [suggestion.title for suggestion in suggestions] == ["Eggs", "Bread"]
	assert default_completed_reminder_suggestion_indexes(suggestions) == {0}


def test_suggest_completed_reminder_items_limits_results_after_ranking() -> None:
	completed_items: list[CompletedReminderItem] = []
	for index in range(60):
		for _repeat in range(60 - index):
			completed_items.append(CompletedReminderItem(title=f"Item {index:02d}", completion_date=None))

	suggestions = suggest_completed_reminder_items(completed_items, existing_items=[])

	assert len(suggestions) == 50
	assert suggestions[0].title == "Item 00"
	assert suggestions[-1].title == "Item 49"


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


def test_apple_reminders_target_falls_back_to_name_when_configured_list_id_is_stale() -> None:
	calls = []

	def fake_runner(args, input, check, capture_output, text):
		calls.append({"args": args, "input": input})
		if args[2] == "list-targets":
			return subprocess.CompletedProcess(
				args,
				0,
				stdout=json.dumps(
					[
						{
							"id": "list-2",
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

	shopping_list = build_shopping_list(
		{"name": "Test Recipe", "ingredients": [{"name": "Apple", "quantity": 1, "always_on_hand": False}]},
		1,
		include_on_hand=False,
	)

	AppleRemindersTarget(runner=fake_runner).create_list(
		shopping_list,
		Config(
			apple_reminders_list_id="deleted-list",
			apple_reminders_list_name="Shared Grocery",
		),
	)

	assert json.loads(calls[1]["input"])["listIdentifier"] == "list-2"


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
