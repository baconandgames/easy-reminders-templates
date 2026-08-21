from __future__ import annotations

import recipe_shopper.cli as shop_script
from recipe_shopper.config import Config, load_config
from recipe_shopper.delivery import DeliveryResult, DeliveryTargetOption
from recipe_shopper.formatter import build_shopping_list


class FakePrompt:
	def __init__(self, result) -> None:
		self.result = result

	def ask(self):
		return self.result


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


def test_select_template_displays_template_names_without_short_names(monkeypatch) -> None:
	template = {"name": "Classic Chili", "short_name": "Chili"}
	captured = {}

	def fake_select(*args, **kwargs):
		captured["choices"] = kwargs["choices"]
		return FakePrompt(template)

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.select_template({"chili": template}) == template
	assert captured["choices"][0].title == "Classic Chili"


def test_prompt_for_include_on_hand_uses_false_default(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(False))

	assert shop_script.prompt_for_include_on_hand(default=False) is False


def test_prompt_for_include_on_hand_uses_true_default(monkeypatch) -> None:
	monkeypatch.setattr(shop_script.questionary, "select", lambda *args, **kwargs: FakePrompt(True))

	assert shop_script.prompt_for_include_on_hand(default=True) is True


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


def test_checked_active_checkbox_row_uses_highlighted_style() -> None:
	control = shop_script.questionary.prompts.common.InquirerControl(
		[shop_script.questionary.Choice(title="Salt", value=0)],
		pointer=">",
	)
	control.selected_options = [0]
	control.pointed_at = 0

	tokens = control._get_choice_tokens()

	assert ("class:highlighted", "[x] ") in tokens
	assert ("class:highlighted", "Salt") in tokens
	assert ("class:selected", "Salt") not in tokens


def test_abort_choice_uses_red_attention_label() -> None:
	choice = shop_script.abort_choice()

	assert choice.title == [("class:abort", "[!] ABORT")]
	assert choice.value == shop_script.ABORT_CHOICE


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
		return FakePrompt(options[1])

	monkeypatch.setattr(shop_script.questionary, "select", fake_select)

	assert shop_script.select_delivery_target("Test", options, omitted_count=2) == options[1]
	assert captured["choices"][0].title == "General (1)"
	assert captured["choices"][1].title == "Test (6) - Bacon"
	assert captured["choices"][2].title == "Test (0)"
	assert captured["default"] == captured["choices"][1]
	assert captured["instruction"] == "2 lists omitted per config.json"


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
		return FakePrompt(["list-1"])

	monkeypatch.setattr(shop_script, "AppleRemindersTarget", FakeAppleRemindersTarget)
	monkeypatch.setattr(shop_script.questionary, "checkbox", fake_checkbox)

	config = shop_script.edit_reminders_list_visibility(
		Config(hidden_apple_reminders_list_ids=["list-2"]),
	)

	assert captured["choices"][0].checked is True
	assert captured["choices"][1].checked is False
	assert config.hidden_apple_reminders_list_ids == ["list-2"]


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

	assert shop_script.run_config_editor(config_path, Config()) == 0
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

	assert shop_script.run_config_editor(config_path, Config()) == 0
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

	assert shop_script.run_config_editor(config_path, Config()) == 0
	assert load_config(config_path).append_short_name is False


def test_exit_config_choice_uses_plain_exit_label() -> None:
	choice = shop_script.exit_config_choice()

	assert choice.title == "Exit Config Menu"
	assert choice.value == shop_script.EXIT_CONFIG_CHOICE


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
	assert captured[1]["qmark"] == "Quantity Color"
	assert captured[1]["default"].value == "green"
	assert captured[1]["instruction"] == (
		"\nUsed for quantities and units in terminal ingredient lists.\n"
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


def test_format_color_setting_instruction_includes_context_and_controls() -> None:
	assert shop_script.format_color_setting_instruction("standard_text_color") == (
		"\nUsed for regular terminal output text.\n"
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
	assert captured[0]["qmark"] == "Options"
	assert captured[0]["instruction"] == shop_script.OPTIONS_MENU_INSTRUCTION
	assert captured[0]["choices"][2].title == "Append Short Name: Yes"
	assert captured[1]["qmark"] == "Append Short Name"
	assert captured[1]["default"].value is True
	assert captured[2]["qmark"] == "Options"


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

	def fake_select_delivery_target(target_name, options, omitted_count=0, prompt_style=None):
		assert target_name == "General"
		assert [option.identifier for option in options] == ["list-1"]
		assert omitted_count == 1
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


def test_format_option_values() -> None:
	assert shop_script.format_bool_option(True) == "Yes"
	assert shop_script.format_bool_option(False) == "No"


def test_print_selected_template_shows_recipe_selection(capsys) -> None:
	shop_script.print_selected_template("Classic Chili")

	assert capsys.readouterr().out == "Select a Template  \033[38;2;255;75;31mClassic Chili\033[0m\n"


def test_format_omitted_list_instruction_pluralizes_lists() -> None:
	assert shop_script.format_omitted_list_instruction(0) == shop_script.SELECT_INSTRUCTION
	assert shop_script.format_omitted_list_instruction(1) == "1 list omitted per config.json"
	assert shop_script.format_omitted_list_instruction(2) == "2 lists omitted per config.json"


def test_render_delivery_result_shows_creation_summary() -> None:
	result = DeliveryResult(
		target_app="apple_reminders",
		target_name="Apple Reminders: Groceries",
		created_items=["5 lb Ground turkey", "9 cans Beans"],
		omitted_items=["3 tsp Salt"],
	)

	assert shop_script.render_delivery_result(result) == (
		"Created: Apple Reminders: Groceries\n"
		"Included: 2 items\n"
		"Omitted: 1 item"
	)


def test_format_delivery_target_option_shows_sample_items() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=6,
		sample_items=["3 28 oz cans Whole tomatoes", "5 lb Ground turkey", "TP"],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (6) - 3 28 oz can..., 5 lb Ground..., TP"


def test_format_delivery_target_option_handles_empty_list() -> None:
	option = DeliveryTargetOption(
		identifier="list-1",
		name="Test",
		source="iCloud",
		item_count=0,
		sample_items=[],
	)

	assert shop_script.format_delivery_target_option(option) == "Test (0)"
