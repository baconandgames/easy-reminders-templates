from __future__ import annotations

import json

import listkit.cli as shop_script
import listkit.app_shell as app_shell
from listkit.config import Config, load_config
from listkit.delivery import DeliveryResult, DeliveryTargetOption
from listkit.formatter import build_shopping_list


class FakePrompt:
	def __init__(self, result) -> None:
		self.result = result

	def ask(self):
		return self.result


def test_main_execs_when_textual_requests_relaunch(monkeypatch, tmp_path) -> None:
	exec_args: list[tuple[str, list[str]]] = []

	def fake_execv(executable: str, args: list[str]) -> None:
		exec_args.append((executable, args))
		raise SystemExit(0)

	monkeypatch.setattr(shop_script.sys, "argv", ["listkit"])
	monkeypatch.setattr(shop_script, "get_project_root", lambda: tmp_path)
	monkeypatch.setattr(shop_script, "resolve_config_path", lambda _project_dir: tmp_path / "config.json")
	monkeypatch.setattr(shop_script, "resolve_templates_path", lambda _project_dir: tmp_path / "templates")
	monkeypatch.setattr(shop_script, "load_config", lambda _config_path: Config())
	monkeypatch.setattr(app_shell, "run_textual_listkit", lambda *_args, **_kwargs: app_shell.RELAUNCH_RESULT_CODE)
	monkeypatch.setattr(shop_script.os, "execv", fake_execv)

	try:
		shop_script.main()
	except SystemExit:
		pass

	assert exec_args == [
		(
			shop_script.sys.executable,
			[shop_script.sys.executable, "-m", "listkit.cli"],
		)
	]


def test_main_treats_settings_like_config(monkeypatch, tmp_path) -> None:
	captured_start_config: list[bool] = []

	def fake_run_textual_listkit(_config, _templates_path, _short_name, _config_path, start_config):
		captured_start_config.append(start_config)
		return 0

	monkeypatch.setattr(shop_script.sys, "argv", ["listkit", "settings"])
	monkeypatch.setattr(shop_script, "get_project_root", lambda: tmp_path)
	monkeypatch.setattr(shop_script, "resolve_config_path", lambda _project_dir: tmp_path / "config.json")
	monkeypatch.setattr(shop_script, "resolve_templates_path", lambda _project_dir: tmp_path / "templates")
	monkeypatch.setattr(shop_script, "load_config", lambda _config_path: Config())
	monkeypatch.setattr(app_shell, "run_textual_listkit", fake_run_textual_listkit)

	assert shop_script.main() == 0
	assert captured_start_config == [True]


def test_resolve_config_path_prefers_project_config(tmp_path) -> None:
	project_dir = tmp_path / "project"
	project_dir.mkdir()
	project_config = project_dir / "config.json"
	project_config.write_text("{}", encoding="utf-8")

	assert shop_script.resolve_config_path(project_dir) == project_config


def test_resolve_config_path_creates_user_config(monkeypatch, tmp_path) -> None:
	project_dir = tmp_path / "project"
	project_dir.mkdir()
	user_data_dir = tmp_path / "user-data"
	monkeypatch.setattr(shop_script, "get_user_data_dir", lambda: user_data_dir)

	config_path = shop_script.resolve_config_path(project_dir)

	assert config_path == user_data_dir / "config.json"
	assert load_config(config_path).standard_text_color == "#f2f0ea"


def test_resolve_templates_path_prefers_project_templates(tmp_path) -> None:
	project_dir = tmp_path / "project"
	project_dir.mkdir()
	project_templates = project_dir / "templates"
	project_templates.mkdir()

	assert shop_script.resolve_templates_path(project_dir) == project_templates


def test_resolve_templates_path_creates_user_templates(monkeypatch, tmp_path) -> None:
	project_dir = tmp_path / "project"
	project_dir.mkdir()
	user_data_dir = tmp_path / "user-data"
	monkeypatch.setattr(shop_script, "get_user_data_dir", lambda: user_data_dir)

	templates_path = shop_script.resolve_templates_path(project_dir)

	assert templates_path == user_data_dir / "templates"
	assert (templates_path / "recipes" / "classic-chili.json").exists()
	assert (templates_path / "lists" / "beach-day.json").exists()


def test_should_show_help_detects_help_flags() -> None:
	assert shop_script.should_show_help(["--help"]) is True
	assert shop_script.should_show_help(["-h"]) is True
	assert shop_script.should_show_help(["chili"]) is False


def test_should_show_version_detects_version_flags() -> None:
	assert shop_script.should_show_version(["--version"]) is True
	assert shop_script.should_show_version(["-V"]) is True
	assert shop_script.should_show_version(["chili"]) is False


def test_render_help_uses_app_color_scheme() -> None:
	help_text = shop_script.render_help(
		Config(
			standard_text_color="white",
			quantity_color="cyan",
			selection_color="red",
			omitted_ingredient_color="grey",
		)
	)

	assert "\033[31mListKit\033[0m" in help_text
	assert "\033[36mlistkit\033[0m chili" in help_text
	assert "\033[36mlistkit\033[0m settings" in help_text
	assert "\033[36mlistkit\033[0m --version" in help_text
	assert "\033[36msettings\033[0m                Open settings" in help_text
	assert "\033[36mtemplate-short-name\033[0m     Optional shortcut for a template" in help_text


def test_render_missing_template_error_lists_available_templates() -> None:
	templates = {
		"classic-chili": {"name": "Classic Chili", "short_name": "chili"},
		"beach-day": {"name": "Beach Day", "short_name": "beach"},
	}

	assert shop_script.render_missing_template_error("chli", templates) == (
		'Error: no template found with short name "chli".\n'
		"\n"
		"Available templates:\n"
		"- Classic Chili [chili]\n"
		"- Beach Day [beach]\n"
		"\n"
		"Run `listkit` to choose from the menu."
	)


def test_format_available_template_omits_empty_short_name() -> None:
	assert shop_script.format_available_template({"name": "Packing", "short_name": ""}) == "Packing"
	assert shop_script.format_available_template({"name": "Packing"}) == "Packing"


def test_select_template_displays_template_names_without_short_names(monkeypatch) -> None:
	template = {"name": "Classic Chili", "short_name": "Chili"}
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		captured["instruction"] = kwargs["instruction"]
		return FakePrompt(template)

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.select_template({"chili": template}) == template
	assert captured["choices"][0].title == "Classic Chili"
	assert captured["instruction"] == shop_script.SELECT_TEMPLATE_INSTRUCTION


def test_select_template_escape_aborts(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(shop_script.ABORT_CHOICE))

	try:
		shop_script.select_template({"chili": {"name": "Classic Chili"}})
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_prompt_for_include_on_hand_uses_false_default(monkeypatch) -> None:
	captured = {}

	def fake_select(*args, **kwargs):
		captured["instruction"] = kwargs["instruction"]
		return FakePrompt(False)

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.prompt_for_include_on_hand(default=False) is False
	assert captured["instruction"] == (
		"\nChoose whether on-hand items should start selected.\n"
		"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]\n"
	)


def test_prompt_for_include_on_hand_uses_true_default(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(True))

	assert shop_script.prompt_for_include_on_hand(default=True) is True


def test_prompt_for_include_on_hand_escape_aborts(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(shop_script.ABORT_CHOICE))

	try:
		shop_script.prompt_for_include_on_hand(default=False)
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_prompt_for_batch_size_returns_questionary_value(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt("1.5"))

	assert shop_script.prompt_for_batch_size({"default_batch": 3}) == 1.5


def test_prompt_for_batch_size_uses_default_on_empty_selection(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt(""))

	assert shop_script.prompt_for_batch_size({"default_batch": 3}) == 3


def test_prompt_for_batch_size_can_abort(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt("q"))

	try:
		shop_script.prompt_for_batch_size({"default_batch": 3})
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_prompt_for_batch_size_escape_aborts(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt(shop_script.ABORT_CHOICE))

	try:
		shop_script.prompt_for_batch_size({"default_batch": 3})
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_prompt_for_ingredient_items_returns_selected_indexes(monkeypatch) -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
			{"name": "Banana", "quantity": 1, "always_on_hand": False},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)
	captured = {}

	def fake_checkbox(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		captured["initial_choice"] = kwargs["initial_choice"]
		return FakePrompt([0, 2])

	monkeypatch.setattr(shop_script.questionary, "checkbox", fake_checkbox)

	assert shop_script.prompt_for_ingredient_items(shopping_list) == [0, 2]
	assert captured["choices"][0].title == "2         Apples"
	assert captured["choices"][0].checked is True
	assert captured["choices"][1].title == "2         Bananas"
	assert captured["choices"][1].checked is True
	assert captured["choices"][2].title == "2 tsp     Salt"
	assert captured["choices"][2].checked is False
	assert captured["initial_choice"] == captured["choices"][2]


def test_apply_selected_ingredients_sets_included_and_omitted_items() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
			{"name": "Banana", "quantity": 1, "always_on_hand": False},
			{"name": "Oil", "quantity": 1, "unit": "tbsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)

	updated = shop_script.apply_selected_ingredients(shopping_list, [0, 2, 3])

	assert [item.name for item in updated.items] == ["Apple", "Banana", "Salt", "Oil"]
	assert [item.name for item in updated.included_items] == ["Apple", "Banana", "Oil"]
	assert [item.name for item in updated.omitted_items] == ["Salt"]
	assert updated.included_items[2].omitted is False


def test_prompt_for_ingredient_items_starts_on_first_item_when_on_hand_is_included(monkeypatch) -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=True)
	captured = {}

	def fake_checkbox(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		captured["initial_choice"] = kwargs["initial_choice"]
		return FakePrompt([0, 1])

	monkeypatch.setattr(shop_script.questionary, "checkbox", fake_checkbox)

	shop_script.prompt_for_ingredient_items(shopping_list)

	assert captured["initial_choice"] == captured["choices"][0]


def test_prompt_for_ingredient_items_escape_aborts(monkeypatch) -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
		],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=True)
	monkeypatch.setattr(shop_script.questionary, "checkbox", lambda *args, **kwargs: FakePrompt(shop_script.ABORT_CHOICE))

	try:
		shop_script.prompt_for_ingredient_items(shopping_list)
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_without_item_tags_removes_display_tags_without_mutating_source() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 1, include_on_hand=False)

	display_list = shop_script.without_item_tags(shopping_list)

	assert display_list.included_items[0].tag is None
	assert display_list.omitted_items[0].tag is None
	assert shopping_list.included_items[0].tag == "Test"


def test_render_final_ingredient_list_excludes_recipe_title() -> None:
	recipe = {
		"name": "Test Recipe",
		"short_name": "Test",
		"ingredients": [
			{"name": "Apple", "quantity": 1, "always_on_hand": False},
			{"name": "Salt", "quantity": 1, "unit": "tsp", "always_on_hand": True},
		],
	}
	shopping_list = build_shopping_list(recipe, 2, include_on_hand=False)
	updated = shop_script.apply_selected_ingredients(shopping_list, [0, 1])
	display_list = shop_script.without_item_tags(updated)

	assert shop_script.render_final_ingredient_list(display_list, shop_script.ColorScheme()) == (
		"\033[38;2;242;240;234mFinal List\033[0m\n"
		"\033[38;2;242;240;234m------------------\033[0m\n"
		"\033[38;2;242;240;234m- \033[38;2;55;183;240m2    \033[0m     Apples\033[0m\n"
		"\033[38;2;242;240;234m- \033[38;2;55;183;240m2 tsp\033[0m     Salt\033[0m"
	)


def test_checked_active_checkbox_row_keeps_semantic_style() -> None:
	control = shop_script.questionary.prompts.common.InquirerControl(
		[shop_script.questionary.Choice(title="Salt", value=0)],
		pointer=">",
	)
	control.selected_options = [0]
	control.pointed_at = 0

	tokens = control._get_choice_tokens()

	assert ("class:pointer", " > ") in tokens
	assert ("class:selected", "[x] ") in tokens
	assert ("class:selected", "Salt") in tokens
	assert ("class:highlighted", "Salt") not in tokens


def test_abort_choice_uses_exit_app_action_label() -> None:
	choice = shop_script.abort_choice()

	assert choice.title == [("class:app-action", "[ ← Exit ListKit ]")]
	assert choice.value == shop_script.ABORT_CHOICE


def test_create_new_list_choice_uses_bracketed_label() -> None:
	choice = shop_script.create_new_list_choice()

	assert choice.title == [("class:app-action", "[ + Create New List ]")]
	assert choice.value.identifier == shop_script.CREATE_NEW_LIST_IDENTIFIER


def test_create_template_from_list_choice_uses_bracketed_label() -> None:
	choice = shop_script.create_template_from_list_choice()

	assert choice.title == [("class:app-action", "[ + Create Template from List ]")]
	assert choice.value == shop_script.CREATE_TEMPLATE_FROM_LIST_CHOICE


def test_select_delivery_target_defaults_to_configured_list_and_details_duplicates(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=["TP"],
		),
		DeliveryTargetOption(
			identifier="list-2",
			name="Test",
			source="iCloud",
			item_count=6,
			sample_items=["Bacon"],
		),
		DeliveryTargetOption(
			identifier="list-3",
			name="Test",
			source="Local",
			item_count=0,
			sample_items=[],
		),
	]
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		captured["default"] = kwargs["default"]
		captured["instruction"] = kwargs["instruction"]
		captured["qmark"] = kwargs["qmark"]
		return FakePrompt(options[1])

	def fake_bind_escape_value(prompt, value) -> None:
		captured["escape_prompt"] = prompt
		captured["escape_value"] = value

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "bind_escape_value", fake_bind_escape_value)

	assert shop_script.select_delivery_target("Test", options, omitted_count=2) == options[1]
	assert captured["choices"][0].title == "General (1)"
	assert captured["choices"][1].title == "Test (6) - Bacon"
	assert captured["choices"][2].title == "Test (0)"
	assert captured["choices"][3].title == [("class:app-action", "[ + Create New List ]")]
	assert captured["default"] == captured["choices"][1]
	assert captured["instruction"] == (
		"\nChoose where the final items should be added.\n"
		"2 lists omitted per config.json\n"
		"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]\n"
	)
	assert captured["qmark"] == "Choose Reminder List"
	assert captured["escape_prompt"] is not None
	assert captured["escape_value"] == shop_script.ABORT_CHOICE


def test_select_delivery_target_prefers_default_identifier_over_name(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="Old Name",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
		DeliveryTargetOption(
			identifier="list-2",
			name="General",
			source="iCloud",
			item_count=0,
			sample_items=[],
		),
	]
	captured = {}

	def fake_select(*args, **kwargs):
		captured["default"] = kwargs["default"]
		return FakePrompt(options[0])

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert (
		shop_script.select_delivery_target(
			"General",
			options,
			default_identifier="list-1",
		)
		== options[0]
	)
	assert captured["default"].value == options[0]


def test_select_delivery_target_can_create_new_list(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]
	target = DeliveryTargetOption(
		identifier="list-2",
		name="Beach",
		source="iCloud",
		item_count=0,
		sample_items=[],
	)

	def fake_select(*args, **kwargs):
		return FakePrompt(kwargs["choices"][1].value)

	class FakeAppleRemindersTarget:
		def create_target(self, list_name):
			assert list_name == "Beach"
			return target

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt("Beach"))
	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)

	assert shop_script.select_delivery_target("General", options) == target


def test_select_delivery_target_can_create_new_list_when_no_lists_exist(monkeypatch) -> None:
	target = DeliveryTargetOption(
		identifier="list-1",
		name="Beach",
		source="iCloud",
		item_count=0,
		sample_items=[],
	)
	captured = {}

	def fake_select(*args, **kwargs):
		raise AssertionError("Expected empty target state to skip the list picker")

	def fake_text(*args, **kwargs):
		captured["instruction"] = kwargs["instruction"]
		return FakePrompt("Beach")

	class FakeAppleRemindersTarget:
		def create_target(self, list_name):
			assert list_name == "Beach"
			return target

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script.questionary, "text", fake_text)
	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)

	assert shop_script.select_delivery_target("General", []) == target
	assert captured["instruction"] == (
		"\nNo visible Reminders lists are available. Enter a name for a new list to continue.\n"
		"[ENTER to create | ESC to exit | Ctrl-C to quit]\n"
	)


def test_select_delivery_target_can_hide_create_new_list_choice(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt(options[0])

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.select_delivery_target("General", options, allow_create_new=False) == options[0]
	assert [choice.value for choice in captured["choices"]] == [options[0], shop_script.ABORT_CHOICE]


def test_select_delivery_target_can_abort(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]

	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(shop_script.ABORT_CHOICE))

	try:
		shop_script.select_delivery_target("General", options)
	except shop_script.ShopAbort:
		pass
	else:
		raise AssertionError("Expected ShopAbort")


def test_select_delivery_target_binds_escape_to_custom_back_choice(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]
	captured = {}

	def fake_select(*args, **kwargs):
		captured["qmark"] = kwargs["qmark"]
		return FakePrompt(options[0])

	def fake_bind_escape_value(prompt, value) -> None:
		captured["escape_prompt"] = prompt
		captured["escape_value"] = value

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "bind_escape_value", fake_bind_escape_value)

	assert (
		shop_script.select_delivery_target(
			"General",
			options,
			qmark="Set Default List",
			exit_choice=shop_script.back_config_choice(),
		)
		== options[0]
	)
	assert captured["qmark"] == "Set Default List"
	assert captured["escape_prompt"] is not None
	assert captured["escape_value"] == shop_script.BACK_CONFIG_CHOICE


def test_prompt_for_new_delivery_target_escape_can_return_back(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "text", lambda *args, **kwargs: FakePrompt(shop_script.BACK_CONFIG_CHOICE))

	assert (
		shop_script.prompt_for_new_delivery_target(escape_value=shop_script.BACK_CONFIG_CHOICE)
		== shop_script.BACK_CONFIG_CHOICE
	)


def test_edit_reminders_list_visibility_stores_hidden_ids(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
		DeliveryTargetOption(
			identifier="list-2",
			name="Archive",
			source="iCloud",
			item_count=0,
			sample_items=[],
		),
	]
	captured = {}

	class FakeAppleRemindersTarget:
		def list_targets(self):
			return options

	def fake_checkbox(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		captured["qmark"] = kwargs["qmark"]
		captured["instruction"] = kwargs["instruction"]
		return FakePrompt(["list-1"])

	def fake_bind_escape_value(prompt, value) -> None:
		captured["escape_prompt"] = prompt
		captured["escape_value"] = value

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(shop_script.questionary, "checkbox", fake_checkbox)
	monkeypatch.setattr(shop_script, "bind_escape_value", fake_bind_escape_value)

	config = shop_script.edit_reminders_list_visibility(
		Config(hidden_apple_reminders_list_ids=["list-2"]),
	)

	assert captured["choices"][0].checked is True
	assert captured["choices"][1].checked is False
	assert captured["qmark"] == "Reminder Lists > Select Lists"
	assert "add/remove lists" in captured["instruction"]
	assert captured["escape_prompt"] is not None
	assert captured["escape_value"] == shop_script.BACK_CONFIG_CHECKBOX_CHOICE
	assert config.hidden_apple_reminders_list_ids == ["list-2"]


def test_edit_reminders_list_visibility_escape_returns_existing_config(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]

	class FakeAppleRemindersTarget:
		def list_targets(self):
			return options

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(
		shop_script.questionary,
		"checkbox",
		lambda *args, **kwargs: FakePrompt(shop_script.BACK_CONFIG_CHECKBOX_CHOICE),
	)

	config = Config(hidden_apple_reminders_list_ids=["list-1"])

	assert shop_script.edit_reminders_list_visibility(config) == config


def test_run_config_editor_returns_to_menu_after_saving(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	menu_results = iter(["reminders_lists", shop_script.EXIT_CONFIG_CHOICE])
	menu_count = 0

	def fake_select(*args, **kwargs):
		nonlocal menu_count
		menu_count += 1
		return FakePrompt(next(menu_results))

	def fake_edit_reminders_list_visibility(config, prompt_style=None):
		return Config(hidden_apple_reminders_list_ids=["list-1"])

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "edit_reminders_list_visibility", fake_edit_reminders_list_visibility)
	monkeypatch.setattr(
		shop_script,
		"get_update_status",
		lambda config: shop_script.UpdateStatus(current_version="0.1.4"),
	)

	assert shop_script.run_config_editor(config_path, Config()) == shop_script.EXIT_CONFIG_CHOICE
	assert menu_count == 2


def test_run_config_editor_saves_color_setting_and_returns_to_menu(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	menu_results = iter(["colors", shop_script.EXIT_CONFIG_CHOICE])

	def fake_select(*args, **kwargs):
		return FakePrompt(next(menu_results))

	def fake_edit_color_settings(config_path, config, prompt_style=None):
		config = Config(quantity_color="cyan")
		shop_script.save_config(config_path, config)
		return config

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "edit_color_settings", fake_edit_color_settings)
	monkeypatch.setattr(
		shop_script,
		"get_update_status",
		lambda config: shop_script.UpdateStatus(current_version="0.1.4"),
	)

	assert shop_script.run_config_editor(config_path, Config()) == shop_script.EXIT_CONFIG_CHOICE
	assert load_config(config_path).quantity_color == "cyan"


def test_run_config_editor_saves_option_setting_and_returns_to_menu(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	menu_results = iter(["options", shop_script.EXIT_CONFIG_CHOICE])

	def fake_select(*args, **kwargs):
		return FakePrompt(next(menu_results))

	def fake_edit_options(config_path, config, prompt_style=None):
		config = Config(append_short_name=False)
		shop_script.save_config(config_path, config)
		return config

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "edit_options", fake_edit_options)
	monkeypatch.setattr(
		shop_script,
		"get_update_status",
		lambda config: shop_script.UpdateStatus(current_version="0.1.4"),
	)

	assert shop_script.run_config_editor(config_path, Config()) == shop_script.EXIT_CONFIG_CHOICE
	assert load_config(config_path).append_short_name is False


def test_run_config_editor_shows_update_badge(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt(shop_script.EXIT_CONFIG_CHOICE)

	def fake_bind_escape_value(prompt, value) -> None:
		captured["escape_prompt"] = prompt
		captured["escape_value"] = value

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)
	monkeypatch.setattr(shop_script, "bind_escape_value", fake_bind_escape_value)
	monkeypatch.setattr(
		shop_script,
		"get_update_status",
		lambda config: shop_script.UpdateStatus(
			current_version="0.1.4",
			latest_release=shop_script.ReleaseInfo(
				version="0.1.5",
				name="Beta polish",
				body="Release notes",
				url="https://github.com/example/release",
			),
		),
	)

	assert shop_script.run_config_editor(config_path, Config()) == shop_script.EXIT_CONFIG_CHOICE
	assert captured["choices"][0].title == "Select Lists"
	assert captured["choices"][1].title == "Set Colors"
	assert captured["choices"][2].title == "Set Defaults"
	assert captured["choices"][3].title == "Check for Updates (1)"
	assert captured["choices"][4].title == [("class:app-action", "[ ↩ Return to ListKit ]")]
	assert captured["choices"][5].title == [("class:app-action", "[ ← Exit Config Menu ]")]
	assert captured["escape_prompt"] is not None
	assert captured["escape_value"] == shop_script.EXIT_CONFIG_CHOICE


def test_handle_update_check_can_skip_release(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	release = shop_script.ReleaseInfo(
		version="0.1.5",
		name="Beta polish",
		body="Release notes",
		url="https://github.com/example/release",
	)
	update_status = shop_script.UpdateStatus(current_version="0.1.4", latest_release=release)

	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt("skip_update"))

	config = shop_script.handle_update_check(config_path, Config(), update_status)

	assert config.skipped_update_version == "0.1.5"
	assert load_config(config_path).skipped_update_version == "0.1.5"


def test_handle_update_check_labels_update_action(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	release = shop_script.ReleaseInfo(
		version="0.1.8",
		name="Beta polish",
		body="Release notes",
		url="https://github.com/example/release",
	)
	update_status = shop_script.UpdateStatus(current_version="0.1.7", latest_release=release)
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt(shop_script.BACK_CONFIG_CHOICE)

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.handle_update_check(config_path, Config(), update_status) == Config()
	assert captured["choices"][0].title == "Update to v0.1.8"
	assert captured["choices"][1].title == "Skip v0.1.8"


def test_handle_update_check_exits_after_copying_update_command(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	release = shop_script.ReleaseInfo(
		version="0.1.8",
		name="Beta polish",
		body="Release notes",
		url="https://github.com/example/release",
	)
	update_status = shop_script.UpdateStatus(current_version="0.1.7", latest_release=release)

	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt("show_command"))
	monkeypatch.setattr(shop_script, "copy_update_command_to_clipboard", lambda: True)

	try:
		shop_script.handle_update_check(config_path, Config(), update_status)
	except shop_script.ConfigExit:
		pass
	else:
		raise AssertionError("Expected ConfigExit")


def test_format_update_command_message_notes_clipboard_copy() -> None:
	assert shop_script.format_update_command_message(copied_to_clipboard=True) == (
		"Update command:\n"
		"pipx upgrade listkit\n"
		"\n"
		"The update command has been copied to your clipboard.\n"
		"listkit will exit now. Paste the command into Terminal, and press Enter."
	)


def test_format_update_command_message_falls_back_without_clipboard() -> None:
	assert shop_script.format_update_command_message(copied_to_clipboard=False) == (
		"Update command:\n"
		"pipx upgrade listkit\n"
		"\n"
		"listkit will exit now. Paste or type this command into Terminal, and press Enter."
	)


def test_render_update_changelog_includes_release_notes() -> None:
	release = shop_script.ReleaseInfo(
		version="0.1.5",
		name="Beta polish",
		body="Release notes",
		url="https://github.com/example/release",
	)

	assert shop_script.render_update_changelog("0.1.4", release) == (
		"Update Available\n"
		"----------------\n"
		"Current: 0.1.4\n"
		"Latest: 0.1.5\n"
		"Release: Beta polish\n"
		"URL: https://github.com/example/release\n"
		"\n"
		"Changelog\n"
		"---------\n"
		"Release notes"
	)


def test_exit_config_choice_uses_app_action_label() -> None:
	choice = shop_script.exit_config_choice()

	assert choice.title == [("class:app-action", "[ ← Exit Config Menu ]")]
	assert choice.value == shop_script.EXIT_CONFIG_CHOICE


def test_return_to_listkit_choice_uses_app_action_label() -> None:
	choice = shop_script.return_to_listkit_choice()

	assert choice.title == [("class:app-action", "[ ↩ Return to ListKit ]")]
	assert choice.value == shop_script.RETURN_TO_LISTKIT_CHOICE


def test_back_config_choice_uses_app_action_label() -> None:
	choice = shop_script.back_config_choice()

	assert choice.title == [("class:app-action", "[ ← Back ]")]
	assert choice.value == shop_script.BACK_CONFIG_CHOICE


def test_edit_color_settings_updates_selected_color_and_returns_to_color_menu(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	results = iter(["quantity_color", "cyan", shop_script.BACK_CONFIG_CHOICE])
	captured = []

	def fake_select(*args, **kwargs):
		captured.append(kwargs)
		return FakePrompt(next(results))

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	config = shop_script.edit_color_settings(config_path, Config(quantity_color="green"))

	assert config.quantity_color == "cyan"
	assert load_config(config_path).quantity_color == "cyan"
	assert captured[0]["qmark"] == "Colors"
	assert captured[0]["instruction"] == shop_script.COLOR_MENU_INSTRUCTION
	assert captured[0]["choices"][1].title == [
		("class:text", "Quantity Color: "),
		("class:color-green", "green"),
	]
	assert captured[1]["qmark"] == "Quantity Color"
	assert captured[1]["default"].value == "green"
	assert captured[1]["instruction"] == (
		"\nUsed for quantities and units in terminal ingredient lists.\n"
		"For custom hex colors, edit config.json directly.\n"
		"[ENTER to save | ESC to return | Ctrl-C to quit]\n"
	)
	assert captured[1]["choices"][0].title == [("#37b7f0", "#37b7f0 (default)")]
	assert captured[1]["choices"][3].title == [("class:color-green", "green")]
	assert captured[2]["qmark"] == "Colors"


def test_edit_color_settings_can_return_to_config_menu(monkeypatch, tmp_path) -> None:
	monkeypatch.setattr(
		shop_script.questionary,
		"select",
		lambda *args, **kwargs: FakePrompt(shop_script.BACK_CONFIG_CHOICE),
	)

	config = Config(quantity_color="green")

	assert shop_script.edit_color_settings(tmp_path / "config.json", config) == config


def test_color_choice_displays_color_name_with_matching_style() -> None:
	choice = shop_script.color_choice("cyan")

	assert choice.title == [("class:color-cyan", "cyan")]
	assert choice.value == "cyan"


def test_color_choice_marks_default_color() -> None:
	choice = shop_script.color_choice("#f2f0ea", is_default=True)

	assert choice.title == [("#f2f0ea", "#f2f0ea (default)")]
	assert choice.value == "#f2f0ea"


def test_format_config_color_value_marks_setting_default() -> None:
	assert shop_script.format_config_color_value(Config(standard_text_color="#f2f0ea"), "standard_text_color") == (
		"#f2f0ea (default)"
	)
	assert shop_script.format_config_color_value(Config(standard_text_color="cyan"), "standard_text_color") == "cyan"
	assert shop_script.format_config_color_value(Config(standard_text_color="default"), "standard_text_color") == (
		"#f2f0ea (default)"
	)


def test_format_config_color_menu_value_does_not_mark_default() -> None:
	assert shop_script.format_config_color_menu_value(Config(standard_text_color="#f2f0ea"), "standard_text_color") == (
		"#f2f0ea"
	)


def test_color_setting_choice_title_colors_only_value() -> None:
	assert shop_script.color_setting_choice_title(
		Config(standard_text_color="#f2f0ea"),
		"Standard Text Color",
		"standard_text_color",
	) == [
		("class:text", "Standard Text Color: "),
		("#f2f0ea", "#f2f0ea"),
	]


def test_format_color_setting_instruction_includes_context_and_controls() -> None:
	assert shop_script.format_color_setting_instruction("standard_text_color") == (
		"\nUsed for regular terminal output text.\n"
		"For custom hex colors, edit config.json directly.\n"
		"[ENTER to save | ESC to return | Ctrl-C to quit]\n"
	)


def test_bind_escape_value_sets_prompt_result() -> None:
	prompt = shop_script.questionary.select(
		"",
		choices=[shop_script.questionary.Choice(title="Back", value=shop_script.BACK_CONFIG_CHOICE)],
	)
	shop_script.bind_escape_value(prompt, shop_script.BACK_CONFIG_CHOICE)

	bindings = prompt.application.key_bindings.get_bindings_for_keys((shop_script.Keys.Escape,))

	assert any(binding.keys == (shop_script.Keys.Escape,) for binding in bindings)


def test_bind_escape_value_handles_text_prompt_key_bindings() -> None:
	prompt = shop_script.questionary.text("")
	shop_script.bind_escape_value(prompt, shop_script.ABORT_CHOICE)

	bindings = prompt.application.key_bindings.get_bindings_for_keys((shop_script.Keys.Escape,))

	assert any(binding.keys == (shop_script.Keys.Escape,) for binding in bindings)


def test_edit_options_updates_boolean_setting_and_returns_to_options_menu(monkeypatch, tmp_path) -> None:
	config_path = tmp_path / "config.json"
	results = iter(["append_short_name", False, shop_script.BACK_CONFIG_CHOICE])
	captured = []

	def fake_select(*args, **kwargs):
		captured.append(kwargs)
		return FakePrompt(next(results))

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	config = shop_script.edit_options(config_path, Config(append_short_name=True))

	assert config.append_short_name is False
	assert load_config(config_path).append_short_name is False
	assert captured[0]["qmark"] == "Set Defaults"
	assert captured[0]["instruction"] == shop_script.OPTIONS_MENU_INSTRUCTION
	assert captured[0]["choices"][2].title == "Append Short Name: Yes"
	assert captured[1]["qmark"] == "Append Short Name"
	assert captured[1]["default"].value is True
	assert captured[1]["instruction"] == (
		"\nChoose whether template short names are appended to reminder items.\n"
		"[↑↓ + ENTER to select | ESC to return | Ctrl-C to quit]\n"
	)
	assert captured[1]["choices"][2].title == [("class:app-action", "[ ← Back ]")]
	assert captured[2]["qmark"] == "Set Defaults"


def test_edit_bool_option_back_returns_existing_config(monkeypatch) -> None:
	monkeypatch.setattr(
		shop_script.questionary,
		"select",
		lambda *args, **kwargs: FakePrompt(shop_script.BACK_CONFIG_CHOICE),
	)

	config = Config(append_short_name=True)

	assert shop_script.edit_bool_option(config, "append_short_name") == config


def test_edit_default_reminders_list_updates_name_and_id(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
		DeliveryTargetOption(
			identifier="list-2",
			name="Test",
			source="iCloud",
			item_count=0,
			sample_items=[],
		),
	]

	class FakeAppleRemindersTarget:
		def list_targets(self):
			return options

	def fake_select_delivery_target(
		target_name,
		options,
		omitted_count=0,
		prompt_style=None,
		qmark="",
		exit_choice=None,
		instruction_description="",
		default_identifier="",
	):
		assert target_name == "General"
		assert [option.identifier for option in options] == ["list-1"]
		assert omitted_count == 1
		assert qmark == "Set Default List"
		assert exit_choice.title == [("class:app-action", "[ ← Back ]")]
		assert instruction_description == "Choose the Reminders list selected by default."
		assert default_identifier == ""
		return options[0]

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(shop_script, "select_delivery_target", fake_select_delivery_target)

	config = shop_script.edit_default_reminders_list(
		Config(
			apple_reminders_list_name="General",
			hidden_apple_reminders_list_ids=["list-2"],
		),
	)

	assert config.apple_reminders_list_id == "list-1"
	assert config.apple_reminders_list_name == "General"


def test_edit_default_reminders_list_back_returns_existing_config(monkeypatch) -> None:
	options = [
		DeliveryTargetOption(
			identifier="list-1",
			name="General",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	]

	class FakeAppleRemindersTarget:
		def list_targets(self):
			return options

	def fake_select_delivery_target(*args, **kwargs):
		return shop_script.BACK_CONFIG_CHOICE

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(shop_script, "select_delivery_target", fake_select_delivery_target)

	config = Config(apple_reminders_list_name="General")

	assert shop_script.edit_default_reminders_list(config) == config


def test_format_option_values() -> None:
	assert shop_script.format_bool_option(True) == "Yes"
	assert shop_script.format_bool_option(False) == "No"


def test_print_selected_template_shows_recipe_selection(capsys) -> None:
	shop_script.print_selected_template("Classic Chili")

	assert capsys.readouterr().out == "Select a Template  \033[38;2;255;75;31mClassic Chili\033[0m\n"


def test_format_delivery_target_instruction_includes_prose_omitted_count_and_controls() -> None:
	assert shop_script.format_delivery_target_instruction("Choose a list.", 2) == (
		"\nChoose a list.\n"
		"2 lists omitted per config.json\n"
		"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]\n"
	)


def test_format_omitted_list_note_pluralizes_lists() -> None:
	assert shop_script.format_omitted_list_note(1) == "1 list omitted per config.json"
	assert shop_script.format_omitted_list_note(2) == "2 lists omitted per config.json"


def test_render_delivery_result_shows_creation_summary() -> None:
	result = DeliveryResult(
		target_app="apple_reminders",
		target_name="Apple Reminders: Groceries",
		created_items=["5 lb Ground turkey", "9 cans Beans"],
		omitted_items=["3 tsp Salt"],
	)

	assert shop_script.render_delivery_result(result) == (
		"\033[90m2 items added to Groceries\033[0m\n"
		"\033[90m1 item omitted\033[0m"
	)


def test_format_delivery_result_list_name_handles_unprefixed_name() -> None:
	assert shop_script.format_delivery_result_list_name("Groceries") == "Groceries"


def test_format_delivery_target_option_shows_sample_items() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=6,
		sample_items=["3 28 oz cans Whole tomatoes", "5 lb Ground turkey", "TP"],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (6) - 3 28 oz can..., 5 lb Ground..., TP"


def test_write_template_from_reminders_list_creates_recipe_capable_list_template(tmp_path) -> None:
	template_path = shop_script.write_template_from_reminders_list(
		tmp_path / "templates",
		"Beach Day",
		"beach-day",
		["Towels", "Sunscreen"],
	)

	assert template_path == tmp_path / "templates" / "lists" / "beach-day.json"
	assert template_path.read_text(encoding="utf-8") == (
		'{\n'
		'  "schema_version": 1,\n'
		'  "type": "list",\n'
		'  "name": "Beach Day",\n'
		'  "short_name": "beach-day",\n'
		'  "default_batch": "",\n'
		'  "items": [\n'
		'    {\n'
		'      "name": "Towels",\n'
		'      "quantity": "",\n'
		'      "unit": "",\n'
		'      "always_on_hand": false\n'
		'    },\n'
		'    {\n'
		'      "name": "Sunscreen",\n'
		'      "quantity": "",\n'
		'      "unit": "",\n'
		'      "always_on_hand": false\n'
		'    }\n'
		'  ]\n'
		'}\n'
	)


def test_write_template_from_reminders_list_uses_available_short_name(tmp_path) -> None:
	first_template_path = shop_script.write_template_from_reminders_list(
		tmp_path / "templates",
		"Ralph's",
		"ralph-s",
		["Milk"],
	)
	second_template_path = shop_script.write_template_from_reminders_list(
		tmp_path / "templates",
		"Ralph's",
		"ralph-s",
		["Eggs"],
	)

	first_template = json.loads(first_template_path.read_text(encoding="utf-8"))
	second_template = json.loads(second_template_path.read_text(encoding="utf-8"))
	assert first_template_path == tmp_path / "templates" / "lists" / "ralph-s.json"
	assert second_template_path == tmp_path / "templates" / "lists" / "ralph-s-2.json"
	assert first_template["short_name"] == "ralph-s"
	assert second_template["short_name"] == "ralph-s-2"


def test_create_template_from_reminders_list_can_skip_completed_item_scan(monkeypatch, tmp_path) -> None:
	class FakeAppleRemindersTarget:
		def list_targets(self) -> list[DeliveryTargetOption]:
			return [
				DeliveryTargetOption(
					identifier="list-1",
					name="Groceries",
					source="iCloud",
					item_count=1,
					sample_items=[],
				)
			]

		def list_items(self, _identifier: str) -> list[str]:
			return ["Milk"]

		def list_completed_items(self, _identifier: str, days: int | None = None):
			raise AssertionError("Completed reminders should not be scanned when skipped.")

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(
		shop_script,
		"select_delivery_target",
		lambda *_args, **_kwargs: DeliveryTargetOption(
			identifier="list-1",
			name="Groceries",
			source="iCloud",
			item_count=1,
			sample_items=[],
		),
	)
	monkeypatch.setattr(shop_script, "prompt_for_completed_item_scan", lambda **_kwargs: False)
	monkeypatch.setattr(shop_script, "prompt_for_template_name", lambda *_args, **_kwargs: "Groceries")
	monkeypatch.setattr(shop_script, "prompt_for_template_short_name", lambda *_args, **_kwargs: "groceries")

	template_path = shop_script.create_template_from_reminders_list(tmp_path / "templates", Config())

	assert template_path == tmp_path / "templates" / "lists" / "groceries.json"
	template_data = json.loads(template_path.read_text(encoding="utf-8"))
	assert [item["name"] for item in template_data["items"]] == ["Milk"]


def test_next_available_template_path_avoids_overwriting_existing_template(tmp_path) -> None:
	lists_path = tmp_path / "lists"
	lists_path.mkdir()
	(lists_path / "beach-day.json").write_text("{}", encoding="utf-8")

	assert shop_script.next_available_template_path(lists_path, "beach-day") == lists_path / "beach-day-2.json"


def test_render_created_template_result_points_to_template_docs(tmp_path) -> None:
	result = shop_script.render_created_template_result(tmp_path / "templates" / "lists" / "beach-day.json")

	assert "Template created:" in result
	assert "See TEMPLATES.md for the template JSON guide." in result


def test_format_delivery_target_option_handles_empty_list() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=0,
		sample_items=[],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (0)"
