from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from textual.widgets import ListView

import listkit.app_shell as app_shell
from listkit.app_shell import ListKitApp, OptionItem
from listkit.config import Config, load_config
from listkit.delivery import CompletedReminderItem, DeliveryTargetOption


def write_template(templates_path: Path) -> None:
	template_path: Path = templates_path / "lists" / "test-list.json"
	template_path.parent.mkdir(parents=True)
	template_path.write_text(
		json.dumps(
			{
				"type": "list",
				"name": "Test List",
				"short_name": "test",
				"items": [
					{"name": "Apples", "quantity": None, "unit": None, "always_on_hand": False},
				],
			}
		),
		encoding="utf-8",
	)


def write_named_template(templates_path: Path, filename: str, name: str, short_name: str) -> None:
	template_path: Path = templates_path / filename
	template_path.parent.mkdir(parents=True, exist_ok=True)
	template_path.write_text(
		json.dumps(
			{
				"type": "list",
				"name": name,
				"short_name": short_name,
				"items": [
					{"name": "Apples", "quantity": None, "unit": None, "always_on_hand": False},
				],
			}
		),
		encoding="utf-8",
	)


def test_app_shell_uses_enter_escape_without_q_quit_binding() -> None:
	keys: set[str] = {binding[0] for binding in ListKitApp.BINDINGS}

	assert "enter" in keys
	assert "escape" in keys
	assert "ctrl+c" in keys
	assert "q" not in keys


def test_main_menu_keeps_exit_listkit_keyboard_accessible(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			list_view = app.query_one(ListView)
			values = [
				item.value
				for item in list_view.children
				if isinstance(item, OptionItem)
			]
			assert "exit" in values

	asyncio.run(run_app())


def test_main_menu_shows_launch_update_shortcut(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(
		ListKitApp,
		"get_update_status",
		lambda self: app_shell.UpdateStatus(
			current_version="0.4.7",
			latest_release=app_shell.ReleaseInfo(version="0.4.8", name="v0.4.8", body="", url=""),
		),
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, check_updates_on_launch=True)
		async with app.run_test() as pilot:
			for _ in range(20):
				await pilot.pause()
				labels = [
					item.label_text
					for item in app.query_one(ListView).children
					if isinstance(item, OptionItem)
				]
				if any("Update Available" in label for label in labels):
					break
			assert "[bold]Update Available: v0.4.7 > v0.4.8[/]" in labels

	asyncio.run(run_app())


def test_template_picker_marks_shared_templates(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	write_named_template(local_path, "local-list.json", "Local List", "local")
	write_named_template(shared_path, "shared-list.json", "Shared List", "shared")

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Local List" in labels
			assert "Shared List (shared)" in labels

	asyncio.run(run_app())


def test_shared_template_with_duplicate_filename_can_coexist_with_local_template(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	write_named_template(local_path, "trip.json", "Local Trip", "local-trip")
	write_named_template(shared_path, "trip.json", "Shared Trip", "shared-trip")

	templates, warning = app_shell.load_app_templates(local_path, str(shared_path))

	assert warning == ""
	assert sorted(templates) == ["external:trip", "trip"]
	assert templates["trip"]["name"] == "Local Trip"
	assert templates["external:trip"]["name"] == "Shared Trip"


def test_duplicate_short_name_opens_disambiguation_picker(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	write_named_template(local_path, "local-beach.json", "Local Beach", "beach")
	write_named_template(shared_path, "shared-beach.json", "Shared Beach", "beach")

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path, short_name="beach")
		async with app.run_test() as pilot:
			await pilot.pause()
			assert app.view_name == "template_short_name_disambiguation"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Local Beach [local] (1) - Apples" in labels
			assert "Shared Beach [shared] (1) - Apples" in labels

	asyncio.run(run_app())


def test_missing_shared_folder_warns_and_keeps_local_templates(tmp_path) -> None:
	local_path = tmp_path / "local"
	write_named_template(local_path, "local-list.json", "Local List", "local")
	missing_shared_path = tmp_path / "missing"

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(missing_shared_path)), local_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Local List" in labels
			assert "Shared template folder is unavailable" in str(app.query_one("#context", app_shell.Static).content)

	asyncio.run(run_app())


def test_invalid_shared_template_warns_and_keeps_valid_shared_templates(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	write_named_template(local_path, "local-list.json", "Local List", "local")
	write_named_template(shared_path, "shared-list.json", "Shared List", "shared")
	(shared_path / "broken.json").write_text("{", encoding="utf-8")

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Local List" in labels
			assert "Shared List (shared)" in labels
			assert "Skipped 1 shared template file" in str(app.query_one("#context", app_shell.Static).content)

	asyncio.run(run_app())


def test_sharing_menu_can_save_and_remove_shared_folder(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	shared_path = tmp_path / "shared"
	shared_path.mkdir()
	config_path = tmp_path / "config.json"

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_sharing_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Current Shared Folder: None" in labels
			assert labels[labels.index("Current Shared Folder: None") + 1] == ""
			assert "Choose Shared Folder" in labels

			monkeypatch.setattr(app_shell, "choose_folder_with_dialog", lambda: str(shared_path))
			app.choose_shared_folder()
			await pilot.pause()
			assert load_config(config_path).external_templates_path == str(shared_path)
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Change Shared Folder" in labels
			assert "Remove Shared Folder" in labels
			assert "Open Shared Folder" in labels

			app.remove_shared_folder()
			await pilot.pause()
			assert load_config(config_path).external_templates_path == ""

	asyncio.run(run_app())


def test_choose_shared_folder_cancel_returns_to_sharing_menu(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(app_shell, "choose_folder_with_dialog", lambda: None)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.choose_shared_folder()
			await pilot.pause()
			assert app.view_name == "config_sharing"
			assert "No shared folder selected." in str(app.query_one("#context", app_shell.Static).content)

	asyncio.run(run_app())


def test_choose_shared_folder_fallback_opens_path_entry(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(app_shell, "choose_folder_with_dialog", lambda: "")

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.choose_shared_folder()
			await pilot.pause()
			assert app.view_name == "config_sharing_path"
			assert "Folder picker unavailable" in str(app.query_one("#context", app_shell.Static).content)

	asyncio.run(run_app())


def test_choose_folder_with_dialog_returns_selected_path() -> None:
	def fake_runner(_command, capture_output, text, check):
		assert capture_output is True
		assert text is True
		assert check is False
		return app_shell.subprocess.CompletedProcess(args=[], returncode=0, stdout="/tmp/shared\n", stderr="")

	assert app_shell.choose_folder_with_dialog(fake_runner) == "/tmp/shared"


def test_choose_folder_with_dialog_returns_none_when_cancelled() -> None:
	def fake_runner(_command, capture_output, text, check):
		return app_shell.subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="User canceled.")

	assert app_shell.choose_folder_with_dialog(fake_runner) is None


def test_new_list_escape_returns_to_target_picker(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=0,
					sample_items=[],
				)
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_new_list_screen()
			await pilot.press("escape")
			await pilot.pause()
			assert app.view_name == "target"
			list_view = app.query_one(ListView)
			labels = [
				item.label_text
				for item in list_view.children
				if isinstance(item, OptionItem)
			]
			assert "Groceries (0)" in labels
			assert "Create New List" in labels

	asyncio.run(run_app())


def test_review_items_enter_opens_target_picker(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=0,
					sample_items=[],
				)
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.start_template(next(iter(app.templates.values())))
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "target"
			list_view = app.query_one(ListView)
			labels = [
				item.label_text
				for item in list_view.children
				if isinstance(item, OptionItem)
			]
			assert "Groceries (0)" in labels

	asyncio.run(run_app())


def test_template_menu_includes_back_item(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "↩ Back" in labels

	asyncio.run(run_app())


def test_template_menu_reloads_templates_from_disk(tmp_path) -> None:
	write_template(tmp_path)
	second_template_path = tmp_path / "lists" / "second-list.json"
	second_template_path.write_text(
		json.dumps(
			{
				"type": "list",
				"name": "Second List",
				"short_name": "second",
				"items": [
					{"name": "Bananas", "quantity": None, "unit": None, "always_on_hand": False},
				],
			}
		),
		encoding="utf-8",
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			(tmp_path / "lists" / "test-list.json").unlink()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Test List" not in labels
			assert "Second List" in labels
			assert "↩ Back" in labels

	asyncio.run(run_app())


def test_template_menu_handles_missing_templates_folder(tmp_path) -> None:
	templates_path = tmp_path / "templates"

	async def run_app() -> None:
		app = ListKitApp(Config(), templates_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			assert app.view_name == "template"
			context = app.query_one("#context")
			assert "No templates found." in str(context.content)
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Create Template from List" in labels
			assert "Open Templates Folder" in labels
			assert "↩ Back" in labels
			assert (templates_path / "lists").exists()
			assert (templates_path / "recipes").exists()

	asyncio.run(run_app())


def test_empty_template_returns_to_template_picker_with_warning(tmp_path) -> None:
	template_path = tmp_path / "lists" / "empty-list.json"
	template_path.parent.mkdir(parents=True)
	template_path.write_text(
		json.dumps(
			{
				"type": "list",
				"name": "Empty List",
				"short_name": "empty",
				"items": [
					{"name": "", "quantity": "", "unit": "", "always_on_hand": False},
				],
			}
		),
		encoding="utf-8",
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.start_template(next(iter(app.templates.values())))
			await pilot.pause()
			assert app.view_name == "template"
			assert 'Template "Empty List" does not have any named items yet.' in str(app.query_one("#context").content)

	asyncio.run(run_app())


def test_missing_short_name_opens_template_picker(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, short_name="missing")
		async with app.run_test() as pilot:
			await pilot.pause()
			assert app.view_name == "template"
			assert app.result_code == 0
			context = app.query_one("#context")
			assert 'Template "missing" was not found.' in str(context.content)
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Test List" in labels
			assert "↩ Back" in labels

	asyncio.run(run_app())


def test_help_screen_includes_documentation_action(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_help()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Open Templates Folder" in labels
			assert "Open Shared Templates Folder" not in labels
			assert "Open Documentation" in labels
			assert "↩ Back" in labels

	asyncio.run(run_app())


def test_help_screen_includes_shared_templates_action_when_configured(tmp_path) -> None:
	write_template(tmp_path)
	shared_path = tmp_path / "shared"
	shared_path.mkdir()

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_help()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Open Templates Folder" in labels
			assert "Open Shared Templates Folder" in labels
			assert "Open Documentation" in labels
			assert "↩ Back" in labels

	asyncio.run(run_app())


def test_start_config_opens_textual_config_menu(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(
		ListKitApp,
		"get_update_status",
		lambda self: app_shell.UpdateStatus(current_version="0.2.0"),
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, start_config=True)
		async with app.run_test() as pilot:
			await pilot.pause()
			assert app.view_name == "config"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Manage Lists" in labels
			assert "Sort Order" in labels
			assert "Usage History" in labels
			assert "Colors" in labels
			assert "Defaults" in labels
			assert "Check for Updates" in labels
			assert "Version 0.2.0" not in labels
			assert "↩ Back" in labels
			assert "Exit ListKit" not in labels

	asyncio.run(run_app())


def test_create_template_from_list_runs_inside_app_shell(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Packing",
					source="iCloud",
					item_count=2,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Socks", "Charger"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			raise AssertionError("Completed reminders should not be scanned when skipped.")

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_scan"

			await pilot.press("down")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_short_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_created_result"
			assert app.result_code == 0

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "packing.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert template_data["name"] == "Packing"
	assert template_data["short_name"] == "packing"
	assert [item["name"] for item in template_data["items"]] == ["Socks", "Charger"]


def test_create_template_source_screen_loads_targets_in_background(monkeypatch, tmp_path) -> None:
	started = threading.Event()
	release = threading.Event()

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			started.set()
			release.wait(timeout=5)
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Packing",
					source="iCloud",
					item_count=2,
					sample_items=[],
				)
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			assert started.wait(timeout=1)
			assert app.view_name == "template_source"
			assert "Loading Reminders lists" in str(app.query_one("#context", app_shell.Static).content)
			assert "Loading Reminders lists..." in str(app.query_one("#body Static", app_shell.Static).content)

			release.set()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == ["Packing (2)", "↩ Back"]

	asyncio.run(run_app())


def test_create_template_from_list_can_scan_completed_items_without_suggestions(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Packing",
					source="iCloud",
					item_count=2,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Socks", "Charger"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			assert days == 180
			return []

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_scan"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_short_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_created_result"
			assert app.result_code == 0

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "packing.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert template_data["name"] == "Packing"
	assert template_data["short_name"] == "packing"
	assert [item["name"] for item in template_data["items"]] == ["Socks", "Charger"]


def test_create_template_from_list_can_add_completed_item_suggestions(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	recent_date: str = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=1,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Milk"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			assert days == 180
			return [
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Bread", completion_date=recent_date),
				CompletedReminderItem(title="Bread", completion_date=recent_date),
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_scan"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_suggestions"
			context = str(app.query_one("#context", app_shell.Static).content)
			assert "detected 2 commonly used items from completed reminders" in context
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == ["[x] Eggs (5)", "[ ] Bread (2)"]

			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_created_result"

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "groceries.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert [item["name"] for item in template_data["items"]] == ["Milk", "Eggs"]


def test_create_template_from_list_can_skip_completed_item_suggestions(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	recent_date: str = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=1,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Milk"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			assert days == 180
			return [
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
				CompletedReminderItem(title="Eggs", completion_date=recent_date),
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_scan"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_suggestions"

			await pilot.press("space")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_created_result"

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "groceries.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert [item["name"] for item in template_data["items"]] == ["Milk"]


def test_create_template_from_list_handles_long_completed_item_suggestion_list(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	recent_date: str = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
	completed_items: list[CompletedReminderItem] = []
	for index in range(1, 59):
		completed_items.extend(
			[
				CompletedReminderItem(title=f"Item {index:02d}", completion_date=recent_date),
				CompletedReminderItem(title=f"Item {index:02d}", completion_date=recent_date),
			]
		)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=1,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Milk"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			assert days == 180
			return completed_items

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_scan"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_completed_suggestions"
			body = app.query_one("#body")
			list_view = app.query_one(ListView)
			assert len(list_view.children) == 50
			assert list_view.region.height == body.region.height
			assert len(app.selected_template_suggestion_indexes) == 50

			await pilot.press("space")
			for _index in range(49):
				await pilot.press("down")
			await pilot.press("space")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_created_result"

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "groceries.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	item_names = [item["name"] for item in template_data["items"]]
	assert len(item_names) == 49
	assert "Milk" in item_names
	assert "Item 01" not in item_names
	assert "Item 50" not in item_names
	assert "Item 51" not in item_names
	assert "Item 02" in item_names


def test_create_template_flow_prompts_for_storage_when_shared_folder_exists(monkeypatch, tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	local_path.mkdir()
	shared_path.mkdir()

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Packing",
					source="iCloud",
					item_count=1,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Socks"]

		def list_completed_items(self, _identifier: str, days: int | None = None) -> list[CompletedReminderItem]:
			return []

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.pause()
			await pilot.press("enter")
			await pilot.press("down")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_storage"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Local Templates Folder" in labels
			assert "Shared Templates Folder" in labels

	asyncio.run(run_app())


def test_create_template_storage_can_save_locally_when_shared_folder_exists(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	local_path.mkdir()
	shared_path.mkdir()

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_short_name = "packing"
			app.template_item_names = ["Socks"]
			app.save_template_to_storage("local")
			await pilot.pause()
			assert app.view_name == "template_created_result"

	asyncio.run(run_app())

	assert (local_path / "lists" / "packing.json").exists()
	assert not (shared_path / "lists" / "packing.json").exists()


def test_create_template_storage_can_save_to_shared_folder(tmp_path) -> None:
	local_path = tmp_path / "local"
	shared_path = tmp_path / "shared"
	local_path.mkdir()
	shared_path.mkdir()

	async def run_app() -> None:
		app = ListKitApp(Config(external_templates_path=str(shared_path)), local_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_short_name = "packing"
			app.template_item_names = ["Socks"]
			app.save_template_to_storage("shared")
			await pilot.pause()
			assert app.view_name == "template_created_result"

	asyncio.run(run_app())

	assert not (local_path / "lists" / "packing.json").exists()
	assert (shared_path / "packing.json").exists()
	assert not (shared_path / "lists" / "packing.json").exists()


def test_created_template_result_shows_summary_and_actions(tmp_path) -> None:
	template_path = tmp_path / "lists" / "packing.json"
	template_path.parent.mkdir()
	template_path.write_text("{}", encoding="utf-8")

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_item_names = ["Socks", "Charger"]
			app.show_created_template_result(template_path)
			await pilot.pause()

			assert app.view_name == "template_created_result"
			body_text = str(app.query_one("#body Static", app_shell.Static).content)
			assert "Name: Packing" in body_text
			assert "Items: 2 items" in body_text
			assert f"File: {template_path}" in body_text
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == ["Open JSON File", "Return to Main Menu"]
			body_children = list(app.query_one("#body").children)
			assert isinstance(body_children[1], app_shell.Static)
			assert str(body_children[1].content) == ""

	asyncio.run(run_app())


def test_created_template_result_can_open_json_file(monkeypatch, tmp_path) -> None:
	template_path = tmp_path / "lists" / "packing.json"
	template_path.parent.mkdir()
	template_path.write_text("{}", encoding="utf-8")
	opened_paths: list[str] = []

	def fake_run(command, check):
		opened_paths.append(command[1])

	monkeypatch.setattr(app_shell.subprocess, "run", fake_run)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_item_names = ["Socks"]
			app.show_created_template_result(template_path)
			await pilot.press("enter")
			await pilot.pause()

	asyncio.run(run_app())

	assert opened_paths == [str(template_path)]


def test_created_template_result_can_return_to_main_menu(tmp_path) -> None:
	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_item_names = ["Socks"]
			app.show_created_template_result(tmp_path / "lists" / "packing.json")
			await pilot.press("down")
			await pilot.press("enter")
			await pilot.pause()

			assert app.view_name == "main"

	asyncio.run(run_app())


def test_created_template_result_escape_returns_to_main_menu(tmp_path) -> None:
	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_name = "Packing"
			app.template_item_names = ["Socks"]
			app.show_created_template_result(tmp_path / "lists" / "packing.json")
			await pilot.press("escape")
			await pilot.pause()

			assert app.view_name == "main"

	asyncio.run(run_app())


def test_write_template_from_empty_reminders_list_creates_blank_item(tmp_path) -> None:
	template_path = app_shell.write_template_from_reminders_list(
		tmp_path,
		"Empty List",
		"empty",
		[],
	)

	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert template_data["items"] == [
		{
			"name": "",
			"quantity": "",
			"unit": "",
			"always_on_hand": False,
		}
	]


def test_write_template_from_reminders_list_can_save_to_root(tmp_path) -> None:
	template_path = app_shell.write_template_from_reminders_list(
		tmp_path,
		"Packing",
		"packing",
		["Socks"],
		use_lists_subfolder=False,
	)

	assert template_path == tmp_path / "packing.json"
	assert not (tmp_path / "lists").exists()


def test_write_template_from_reminders_list_uses_available_short_name(tmp_path) -> None:
	first_template_path = app_shell.write_template_from_reminders_list(
		tmp_path,
		"Ralph's",
		"ralph-s",
		["Milk"],
	)
	second_template_path = app_shell.write_template_from_reminders_list(
		tmp_path,
		"Ralph's",
		"ralph-s",
		["Eggs"],
	)

	first_template = json.loads(first_template_path.read_text(encoding="utf-8"))
	second_template = json.loads(second_template_path.read_text(encoding="utf-8"))
	assert first_template_path == tmp_path / "lists" / "ralph-s.json"
	assert second_template_path == tmp_path / "lists" / "ralph-s-2.json"
	assert first_template["short_name"] == "ralph-s"
	assert second_template["short_name"] == "ralph-s-2"


def test_load_app_templates_allows_duplicate_local_short_names(tmp_path) -> None:
	write_named_template(tmp_path, "ralph-s.json", "Ralph's", "ralph-s")
	write_named_template(tmp_path, "ralph-s-2.json", "Ralph's", "ralph-s")

	templates, warning = app_shell.load_app_templates(tmp_path, "")

	assert sorted(templates) == ["ralph-s", "ralph-s-2"]
	assert warning == ""


def test_duplicate_local_short_name_opens_disambiguation_picker(tmp_path) -> None:
	write_named_template(tmp_path, "ralph-s.json", "Ralph's", "ralph-s")
	write_named_template(tmp_path, "ralph-s-2.json", "Ralph's 2", "ralph-s")

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, short_name="ralph-s")
		async with app.run_test() as pilot:
			await pilot.pause()
			assert app.view_name == "template_short_name_disambiguation"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Ralph's [local] (1) - Apples" in labels
			assert "Ralph's 2 [local] (1) - Apples" in labels

	asyncio.run(run_app())


def test_template_short_name_collision_refreshes_with_available_suggestion(tmp_path) -> None:
	write_named_template(tmp_path, "ralph-s.json", "Ralph's", "ralph-s")

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.template_source_target = DeliveryTargetOption("target-id", "Ralph's", "iCloud", 0, [])
			app.template_name = "Ralph's"
			app.show_template_short_name_screen()
			await pilot.pause()
			app.submit_template_short_name("ralph-s")
			await pilot.pause()

			assert app.view_name == "template_short_name"
			assert 'Short name "ralph-s" unavailable.' in str(app.query_one("#context", app_shell.Static).content)
			assert app.query_one("#template-short-name-input", app_shell.Input).value == "ralph-s-2"

	asyncio.run(run_app())


def test_check_for_updates_refreshes_inline_when_current(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	statuses = [
		app_shell.UpdateStatus(current_version="0.2.0"),
		app_shell.UpdateStatus(current_version="0.2.0"),
	]

	def fake_get_update_status(self) -> app_shell.UpdateStatus:
		return statuses.pop(0)

	monkeypatch.setattr(ListKitApp, "get_update_status", fake_get_update_status)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, start_config=True)
		async with app.run_test() as pilot:
			await pilot.pause()
			await pilot.press("down", "down", "down", "down", "down", "enter")
			await pilot.pause()
			assert app.view_name == "config"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Check for Updates: up to date" in labels

	asyncio.run(run_app())


def test_config_bool_option_saves_from_keyboard(tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	async def run_app() -> None:
		app = ListKitApp(Config(append_short_name=True), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			app.show_config_bool_option("append_short_name")
			await pilot.press("down", "enter")
			await pilot.pause()
			assert app.view_name == "config_defaults"

	asyncio.run(run_app())

	assert load_config(config_path).append_short_name is False


def test_config_list_visibility_saves_from_keyboard(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="target-id",
					name="Groceries",
					source="iCloud",
					item_count=0,
					sample_items=[],
				)
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			app.show_config_list_visibility()
			await pilot.press("space", "enter")
			await pilot.pause()
			assert app.view_name == "config"

	asyncio.run(run_app())

	assert load_config(config_path).hidden_apple_reminders_list_ids == ["target-id"]


def test_config_color_picker_saves_from_keyboard(tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	async def run_app() -> None:
		app = ListKitApp(Config(quantity_color="green"), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			app.show_config_color_picker("quantity_color")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "config_colors"

	asyncio.run(run_app())

	assert load_config(config_path).quantity_color == Config.quantity_color


def test_sort_order_picker_saves_template_sort_order(tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			app.show_config_sort_order_picker("template_sort_order")
			await pilot.pause()
			await pilot.press("down", "enter")
			await pilot.pause()
			assert app.view_name == "config_sort_order"

	asyncio.run(run_app())

	assert load_config(config_path).template_sort_order == "name_desc"


def test_sort_order_screens_include_back_rows(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_config_sort_order_menu()
			await pilot.pause()
			sort_menu_labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "↩ Back" in sort_menu_labels

			app.show_config_sort_order_picker("template_sort_order")
			await pilot.pause()
			template_picker_labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "↩ Back" in template_picker_labels
			assert "Item Count Ascending" not in template_picker_labels
			assert "Item Count Descending" not in template_picker_labels

			app.show_config_sort_order_picker("reminders_list_sort_order")
			await pilot.pause()
			list_picker_labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "↩ Back" in list_picker_labels
			assert "Item Count Ascending" in list_picker_labels
			assert "Item Count Descending" in list_picker_labels

	asyncio.run(run_app())


def test_template_menu_uses_configured_sort_order(tmp_path) -> None:
	write_template(tmp_path)
	second_template_path = tmp_path / "lists" / "big-list.json"
	second_template_path.write_text(
		json.dumps(
			{
				"type": "list",
				"name": "Big List",
				"short_name": "big",
				"items": [
					{"name": "Bananas", "quantity": None, "unit": None, "always_on_hand": False},
					{"name": "Carrots", "quantity": None, "unit": None, "always_on_hand": False},
				],
			}
		),
		encoding="utf-8",
	)

	async def run_app() -> None:
		app = ListKitApp(Config(template_sort_order="name_desc"), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_template_menu()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels[:2] == ["Test List", "Big List"]

	asyncio.run(run_app())


def test_reminders_list_pickers_use_configured_sort_order(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption("small-id", "Small", "iCloud", 1, []),
				DeliveryTargetOption("large-id", "Large", "iCloud", 3, []),
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(reminders_list_sort_order="item_count_desc"), tmp_path)
		async with app.run_test() as pilot:
			app.show_config_list_visibility()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels[:2] == ["[x] Large (3)", "[x] Small (1)"]

	asyncio.run(run_app())


def test_sort_helpers_support_requested_modes() -> None:
	templates = {
		"small": {"name": "Small", "items": [{"name": "A"}]},
		"large": {"name": "Large", "items": [{"name": "A"}, {"name": ""}, {"name": "B"}]},
	}
	targets = [
		DeliveryTargetOption("small-id", "Small", "iCloud", 1, []),
		DeliveryTargetOption("large-id", "Large", "iCloud", 3, []),
	]

	assert [template["name"] for _id, template in app_shell.sort_templates(templates, "name_desc")] == ["Small", "Large"]
	assert [template["name"] for _id, template in app_shell.sort_templates(templates, "most_frequently_used", {"small": {"name": "Small", "count": 2}})] == ["Small", "Large"]
	assert [target.name for target in app_shell.sort_reminders_targets(targets, "item_count_desc")] == ["Large", "Small"]
	assert [target.name for target in app_shell.sort_reminders_targets(targets, "most_frequently_used", {"small-id": {"name": "Small", "count": 2}})] == ["Small", "Large"]
	assert app_shell.template_item_count(templates["large"]) == 2
	assert app_shell.format_target_label(DeliveryTargetOption("unknown-id", "Unknown", "iCloud", -1, []), show_detail=True) == "Unknown"


def test_successful_reminder_creation_records_usage(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	class FakeAppleRemindersTarget:
		def create_list(self, shopping_list, _config):
			return app_shell.DeliveryResult(
				target_app="apple_reminders",
				target_name="Apple Reminders: Groceries",
				created_items=[item.name for item in shopping_list.included_items],
				omitted_items=[],
			)

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.start_template(next(iter(app.templates.values())), "lists/test-list")
			app.delivery_target = DeliveryTargetOption("target-id", "Groceries", "iCloud", 0, [])
			app.create_reminders()
			await pilot.pause()
			assert app.view_name == "result"

	asyncio.run(run_app())

	config = load_config(config_path)
	assert config.template_usage_counts == {"lists/test-list": {"name": "Test List", "count": 1}}
	assert config.reminders_list_usage_counts == {"target-id": {"name": "Groceries", "count": 1}}


def test_reminder_creation_suppresses_buffered_continue_input(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def create_list(self, shopping_list, _config):
			return app_shell.DeliveryResult(
				target_app="apple_reminders",
				target_name="Apple Reminders: Groceries",
				created_items=[item.name for item in shopping_list.included_items],
				omitted_items=[],
			)

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.start_template(next(iter(app.templates.values())), "test-list")
			app.delivery_target = DeliveryTargetOption("target-id", "Groceries", "iCloud", 0, [])
			app.create_reminders()
			assert app.view_name == "result"
			app.action_continue()
			assert app.view_name == "result"
			app.suppress_input_until = 0.0
			app.action_continue()
			assert app.view_name == "template"

	asyncio.run(run_app())


def test_reminders_busy_state_clears_after_delivery_error(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def create_list(self, _shopping_list, _config):
			raise app_shell.DeliveryError("Reminders unavailable")

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.start_template(next(iter(app.templates.values())), "test-list")
			app.delivery_target = DeliveryTargetOption("target-id", "Groceries", "iCloud", 0, [])
			app.create_reminders()
			assert app.view_name == "error"
			assert app.reminders_operation_running is False

	asyncio.run(run_app())


def test_usage_history_screens_show_counts_and_actions(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption("target-id", "Groceries", "iCloud", 0, []),
			]

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(
			Config(
				template_usage_counts={"lists/test-list": {"name": "Test List", "count": 3}},
				reminders_list_usage_counts={"target-id": {"name": "Groceries", "count": 2}},
			),
			tmp_path,
		)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_usage_history_menu()
			await pilot.pause()
			usage_menu_labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert "Template Usage" in usage_menu_labels
			assert "Reminders List Usage" in usage_menu_labels
			assert "Open config.json" not in usage_menu_labels
			assert "↩ Back" in usage_menu_labels

			app.show_template_usage_history()
			await pilot.pause()
			template_list = app.query_one(ListView)
			template_labels = [
				item.label_text
				for item in template_list.children
				if isinstance(item, OptionItem)
			]
			assert "------------------------------------" in template_labels
			assert "Test List: 3" in template_labels
			assert "Reset All to Zero" in template_labels
			assert "Open config.json" in template_labels
			assert template_labels.index("") == template_labels.index("Open config.json") - 1
			assert template_labels[template_list.index or 0] == "Open config.json"
			assert "↩ Back" in template_labels

			app.show_list_usage_history()
			await pilot.pause()
			list_view = app.query_one(ListView)
			list_labels = [
				item.label_text
				for item in list_view.children
				if isinstance(item, OptionItem)
			]
			assert "------------------------------------" in list_labels
			assert "Groceries: 2" in list_labels
			assert "Reset All to Zero" in list_labels
			assert "Open config.json" in list_labels
			assert list_labels.index("") == list_labels.index("Open config.json") - 1
			assert list_labels[list_view.index or 0] == "Open config.json"
			assert "↩ Back" in list_labels

	asyncio.run(run_app())


def test_reset_usage_history_clears_selected_counts(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"

	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return []

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(
			Config(
				template_usage_counts={"lists/test-list": {"name": "Test List", "count": 3}},
				reminders_list_usage_counts={"target-id": {"name": "Groceries", "count": 2}},
			),
			tmp_path,
			config_path=config_path,
		)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_reset_usage_confirmation("template")
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "config_template_usage"

	asyncio.run(run_app())

	config = load_config(config_path)
	assert config.template_usage_counts == {}
	assert config.reminders_list_usage_counts == {"target-id": {"name": "Groceries", "count": 2}}


def test_reset_usage_confirmation_uses_confirm_cancel_options(tmp_path) -> None:
	write_template(tmp_path)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_reset_usage_confirmation("template")
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == ["Confirm Reset", "Cancel"]

	asyncio.run(run_app())


def test_open_config_file_creates_file_and_uses_os_open(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	config_path = tmp_path / "config.json"
	opened_paths: list[str] = []

	def fake_run(command, check):
		opened_paths.append(command[1])

	monkeypatch.setattr(app_shell.subprocess, "run", fake_run)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, config_path=config_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.open_config_file()
			await pilot.pause()

	asyncio.run(run_app())

	assert opened_paths == [str(config_path)]
	assert config_path.exists()


def test_usage_history_formatters_sort_counts() -> None:
	templates = {
		"small": {"name": "Small"},
		"large": {"name": "Large"},
		"unused": {"name": "Unused"},
	}
	targets = [
		DeliveryTargetOption("small-id", "Small", "iCloud", 0, []),
		DeliveryTargetOption("large-id", "Large", "iCloud", 0, []),
		DeliveryTargetOption("unused-id", "Unused", "iCloud", 0, []),
	]

	assert app_shell.format_template_usage_rows(templates, {"small": {"name": "Small", "count": 1}, "large": {"name": "Large", "count": 3}}) == [
		"------------------------------------",
		"Large: 3",
		"Small: 1",
		"Unused: 0",
	]
	assert app_shell.format_reminders_list_usage_rows(targets, {"small-id": {"name": "Small", "count": 1}, "large-id": {"name": "Large", "count": 3}}) == [
		"------------------------------------",
		"Large: 3",
		"Small: 1",
		"Unused: 0",
	]
	assert app_shell.format_template_usage_rows(templates, {}) == [
		"------------------------------------",
		"Large: 0",
		"Small: 0",
		"Unused: 0",
	]


def test_render_created_items_summary_lists_created_items() -> None:
	assert app_shell.render_created_items_summary(["Apples", "2 lb Rice"]) == (
		"------------------------------------\n"
		"- Apples\n"
		"- 2 lb Rice"
	)


def test_color_labels_include_rich_color_markup() -> None:
	assert app_shell.format_color_setting_label(Config(quantity_color="#37b7f0"), "quantity_color") == (
		"Quantity Color: [#37b7f0]#37b7f0[/]"
	)
	assert app_shell.format_color_choice_label("magenta", False) == "[#ff2dcb]magenta[/]"
	assert app_shell.format_color_choice_label("#f2f0ea", True) == "[#f2f0ea]#f2f0ea[/] (default)"


def test_update_menu_label_shows_inline_status() -> None:
	assert app_shell.format_update_menu_label(app_shell.UpdateStatus(current_version="0.2.0")) == (
		"Check for Updates"
	)
	assert app_shell.format_update_menu_label(app_shell.UpdateStatus(current_version="0.2.0"), True) == (
		"Check for Updates: up to date"
	)
	assert app_shell.format_update_menu_label(app_shell.UpdateStatus(current_version="0.2.0", error="offline"), True) == (
		"Check for Updates: unavailable"
	)
	assert app_shell.format_update_menu_label(
		app_shell.UpdateStatus(
			current_version="0.2.0",
			latest_release=app_shell.ReleaseInfo(version="0.3.0", name="v0.3.0", body="", url=""),
		)
	) == "Update to v0.3.0"


def test_settings_context_shows_version_status() -> None:
	assert app_shell.format_settings_context(app_shell.UpdateStatus(current_version="0.2.0")) == (
		"Choose what you want to configure. v0.2.0 is up to date."
	)
	assert app_shell.format_settings_context(
		app_shell.UpdateStatus(
			current_version="0.2.0",
			latest_release=app_shell.ReleaseInfo(version="0.3.0", name="v0.3.0", body="", url=""),
		)
	) == "Choose what you want to configure.\nUpdate available: v0.2.0 > v0.3.0."


def test_update_screen_includes_release_link(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(
		ListKitApp,
		"get_update_status",
		lambda self: app_shell.UpdateStatus(
			current_version="0.2.0",
			latest_release=app_shell.ReleaseInfo(
				version="0.3.0",
				name="v0.3.0",
				body="Release notes",
				url="https://github.com/example/release",
			),
		),
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path, start_config=True)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.show_update_screen()
			await pilot.pause()
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == [
				"Update to v0.3.0",
				"View Release on GitHub",
				"Skip v0.3.0",
				"↩ Back",
			]

	asyncio.run(run_app())


def test_run_update_shows_success_restart_screen(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	monkeypatch.setattr(
		app_shell,
		"run_package_update",
		lambda version: app_shell.UpdateResult(
			success=True,
			command=("pipx", "install", "--force", f"git+repo@v{version}"),
			output="ok",
		),
	)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.update_release = app_shell.ReleaseInfo(
				version="0.3.0",
				name="v0.3.0",
				body="",
				url="https://github.com/example/release",
			)
			app.run_update()
			for _ in range(20):
				await pilot.pause()
				if app.view_name == "config_update_success":
					break
			assert app.view_name == "config_update_success"
			labels = [
				item.label_text
				for item in app.query_one(ListView).children
				if isinstance(item, OptionItem)
			]
			assert labels == ["Quit and Relaunch"]

	asyncio.run(run_app())


def test_relaunch_exits_with_relaunch_result_code(monkeypatch, tmp_path) -> None:
	app = ListKitApp(Config(), tmp_path)
	exit_codes: list[int] = []
	monkeypatch.setattr(app, "exit", lambda code=0: exit_codes.append(code))

	app.relaunch()

	assert exit_codes == [app_shell.RELAUNCH_RESULT_CODE]


def test_view_release_opens_default_browser(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	opened_urls: list[str] = []
	monkeypatch.setattr(app_shell.webbrowser, "open", lambda url: opened_urls.append(url))

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.update_release = app_shell.ReleaseInfo(
				version="0.3.0",
				name="v0.3.0",
				body="",
				url="https://github.com/example/release",
			)
			app.view_release_on_github()
			await pilot.pause()

	asyncio.run(run_app())

	assert opened_urls == ["https://github.com/example/release"]


def test_copy_error_and_open_issue(monkeypatch, tmp_path) -> None:
	write_template(tmp_path)
	copied_text: list[str] = []
	opened_urls: list[str] = []
	monkeypatch.setattr(app_shell, "copy_text_to_clipboard", lambda text: copied_text.append(text) or True)
	monkeypatch.setattr(app_shell.webbrowser, "open", lambda url: opened_urls.append(url))

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.update_result = app_shell.UpdateResult(
				success=False,
				command=("pipx", "upgrade", "listkit"),
				output="failed output",
				error="Command exited with 1.",
			)
			app.copy_update_error(open_issue=True)
			await pilot.pause()

	asyncio.run(run_app())

	assert "failed output" in copied_text[0]
	assert opened_urls == [app_shell.GITHUB_ISSUES_URL]
