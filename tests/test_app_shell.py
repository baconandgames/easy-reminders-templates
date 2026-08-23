from __future__ import annotations

import asyncio
import json
from pathlib import Path

from textual.widgets import ListView

import recipe_shopper.app_shell as app_shell
from recipe_shopper.app_shell import ListKitApp, OptionItem
from recipe_shopper.config import Config, load_config
from recipe_shopper.delivery import DeliveryTargetOption


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

	monkeypatch.setattr(app_shell, "AppleRemindersTarget", FakeAppleRemindersTarget)

	async def run_app() -> None:
		app = ListKitApp(Config(), tmp_path)
		async with app.run_test() as pilot:
			app.show_create_template_source_screen()
			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "template_short_name"

			await pilot.press("enter")
			await pilot.pause()
			assert app.view_name == "result"
			assert app.result_code == 0

	asyncio.run(run_app())

	template_path = tmp_path / "lists" / "packing.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert template_data["name"] == "Packing"
	assert template_data["short_name"] == "packing"
	assert [item["name"] for item in template_data["items"]] == ["Socks", "Charger"]


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
	) == "Choose what you want to configure. v0.3.0 is available."


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
				command=("pipx", "upgrade", "easy-reminder-templates"),
				output="failed output",
				error="Command exited with 1.",
			)
			app.copy_update_error(open_issue=True)
			await pilot.pause()

	asyncio.run(run_app())

	assert "failed output" in copied_text[0]
	assert opened_urls == [app_shell.GITHUB_ISSUES_URL]
