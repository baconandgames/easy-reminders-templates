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
			await pilot.press("down", "down", "down", "enter")
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
