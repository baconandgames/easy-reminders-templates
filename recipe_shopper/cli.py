#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

try:
	import questionary
	from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
	from prompt_toolkit.keys import Keys
except ModuleNotFoundError:
	project_dir: Path = Path(__file__).resolve().parents[1]
	project_venv: Path = project_dir / ".venv"
	project_python: Path = project_venv / "bin" / "python"
	if project_python.exists() and Path(sys.prefix).resolve() != project_venv.resolve():
		os.execv(str(project_python), [str(project_python), *sys.argv])

	raise SystemExit(
		"Error: missing dependency questionary. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
	)

from recipe_shopper.colors import NAMED_COLORS, normalize_color, prompt_color_style, terminal_color_code
from recipe_shopper.config import Config, ConfigLoadError, load_config, save_config
from recipe_shopper.delivery import (
	AppleRemindersTarget,
	CREATE_NEW_LIST_IDENTIFIER,
	DeliveryError,
	DeliveryResult,
	DeliveryTargetOption,
)
from recipe_shopper.formatter import (
	ColorScheme,
	ShoppingList,
	ShoppingListItem,
	build_shopping_list,
	calculate_line_width,
	format_item,
	format_item_prefix,
	format_number,
	style_text,
)
from recipe_shopper.templates import (
	TemplateLoadError,
	find_template_by_short_name,
	load_templates,
	template_has_on_hand_items,
	template_uses_batch_size,
)
from recipe_shopper.updates import (
	UPDATE_COMMAND,
	ReleaseInfo,
	UpdateCheckError,
	fetch_latest_release,
	get_current_version,
	is_newer_version,
)


def format_prompt_instruction(prose: str, controls: str) -> str:
	return f"\n{prose}\n{controls}\n"


ABORT_COMMANDS: set[str] = {"q", "quit", "cancel", "abort"}
ABORT_CHOICE: str = "__abort__"
ABORT_TITLE: str = "[ ← Exit ListKit ]"
CREATE_NEW_LIST_TITLE: str = "[ + Create New List ]"
CREATE_TEMPLATE_FROM_LIST_CHOICE: str = "__create_template_from_list__"
CREATE_TEMPLATE_FROM_LIST_TITLE: str = "[ + Create Template from List ]"
EXIT_CONFIG_CHOICE: str = "__exit_config__"
EXIT_CONFIG_TITLE: str = "[ ← Exit Config Menu ]"
RETURN_TO_LISTKIT_CHOICE: str = "__return_to_listkit__"
RETURN_TO_LISTKIT_TITLE: str = "[ ↩ Return to ListKit ]"
BACK_CONFIG_CHOICE: str = "__back_config__"
BACK_CONFIG_CHECKBOX_CHOICE: list[str] = [BACK_CONFIG_CHOICE]
BACK_CONFIG_TITLE: str = "[ ← Back ]"
MAIN_FLOW_DESCRIPTION: str = "Choose a template, adjust its items, then send the final list to Reminders."
SELECT_TEMPLATE_INSTRUCTION: str = format_prompt_instruction(
	MAIN_FLOW_DESCRIPTION,
	"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]",
)
TEMPLATE_NAME_INSTRUCTION: str = format_prompt_instruction(
	"Enter the name to use for this ListKit template.",
	"[ENTER to save | ESC to return | Ctrl-C to quit]",
)
TEMPLATE_SHORT_NAME_INSTRUCTION: str = format_prompt_instruction(
	"Enter an optional shortcut for running this template from Terminal.",
	"[ENTER to save | ESC to return | Ctrl-C to quit]",
)
CONFIG_MENU_INSTRUCTION: str = format_prompt_instruction(
	"Change ListKit settings or return to list creation.",
	"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]",
)
INGREDIENT_INSTRUCTION: str = format_prompt_instruction(
	"Select the items that should be added to the final Reminders list.",
	"[SPACE to include/exclude items | ENTER to continue | ESC to exit | Ctrl-C to quit]",
)
CONFIG_LIST_INSTRUCTION: str = format_prompt_instruction(
	"Choose which Reminders lists appear when creating a list.",
	"[SPACE to add/remove lists | ENTER to save | ESC to return | Ctrl-C to quit]",
)
COLOR_MENU_INSTRUCTION: str = format_prompt_instruction(
	"Choose the colors used by ListKit prompts and terminal output.",
	"[↑↓ + ENTER to edit | ESC to return | Ctrl-C to quit]",
)
COLOR_PICKER_CONTROLS: str = "[ENTER to save | ESC to return | Ctrl-C to quit]"
COLOR_PICKER_HEX_NOTE: str = "For custom hex colors, edit config.json directly."
OPTIONS_MENU_INSTRUCTION: str = format_prompt_instruction(
	"Choose the default behavior used when creating lists.",
	"[↑↓ + ENTER to edit | ESC to return | Ctrl-C to quit]",
)
UPDATE_MENU_INSTRUCTION: str = format_prompt_instruction(
	"Review this release, then update, skip, or go back.",
	"[↑↓ + ENTER to select | ESC to return | Ctrl-C to quit]",
)
TRUNCATED_SAMPLE_LENGTH: int = 11
CONFIG_COLOR_OPTIONS: tuple[str, ...] = (
	"black",
	"red",
	"green",
	"yellow",
	"blue",
	"magenta",
	"cyan",
	"white",
	"grey",
)
CONFIG_COLOR_DEFAULTS: dict[str, str] = {
	"standard_text_color": Config.standard_text_color,
	"quantity_color": Config.quantity_color,
	"selection_color": Config.selection_color,
	"omitted_ingredient_color": Config.omitted_ingredient_color,
}
COLOR_SETTING_INSTRUCTIONS: dict[str, str] = {
	"standard_text_color": "Used for regular terminal output text.",
	"quantity_color": "Used for quantities and units in terminal ingredient lists.",
	"selection_color": "Used for active menu rows and selected prompt answers.",
	"omitted_ingredient_color": "Used for ingredients excluded from the final list.",
}
APP_NAME: str = "Easy Reminder Templates"


class ShopAbort(Exception):
	pass


class ConfigExit(Exception):
	pass


@dataclass(frozen=True)
class UpdateStatus:
	current_version: str
	latest_release: ReleaseInfo | None = None
	skipped_release: ReleaseInfo | None = None
	error: str = ""


def configure_questionary_checkbox_rendering() -> None:
	common = questionary.prompts.common
	common.INDICATOR_SELECTED = "[x]"
	common.INDICATOR_UNSELECTED = "[ ]"

	def get_choice_tokens(self):
		tokens = []

		def append(index, choice):
			selected = choice.value in self.selected_options
			pointed_at = index == self.pointed_at

			if pointed_at:
				if self.pointer is not None:
					tokens.append(("class:pointer", f" {self.pointer} "))
				else:
					tokens.append(("class:text", " " * 3))

				tokens.append(("[SetCursorPosition]", ""))
			else:
				pointer_length = len(self.pointer) if self.pointer is not None else 1
				tokens.append(("class:text", " " * (2 + pointer_length)))

			if isinstance(choice, common.Separator):
				tokens.append(("class:separator", f"{choice.title}"))
			elif choice.disabled:
				disabled_style = "class:selected" if selected else "class:disabled"
				if isinstance(choice.title, list):
					tokens.append((disabled_style, "- "))
					tokens.extend(choice.title)
				else:
					tokens.append((disabled_style, f"- {choice.title}"))

				disabled_text = "" if isinstance(choice.disabled, bool) else f" ({choice.disabled})"
				tokens.append((disabled_style, disabled_text))
			else:
				shortcut = choice.get_shortcut_title() if self.use_shortcuts else ""

				if selected:
					indicator = f"{common.INDICATOR_SELECTED} " if self.use_indicator else ""
					indicator_style = "class:selected"
				else:
					indicator = f"{common.INDICATOR_UNSELECTED} " if self.use_indicator else ""
					indicator_style = "class:text"

				tokens.append((indicator_style, indicator))

				if isinstance(choice.title, list):
					tokens.extend(choice.title)
				elif selected:
					tokens.append(("class:selected", f"{shortcut}{choice.title}"))
				else:
					tokens.append(("class:text", f"{shortcut}{choice.title}"))

			tokens.append(("", "\n"))

		for index, choice in enumerate(self.filtered_choices):
			append(index, choice)

		current = self.get_pointed_at()

		if self.show_selected:
			answer = current.get_shortcut_title() if self.use_shortcuts else ""
			answer += current.title if isinstance(current.title, str) else "".join(token[1] for token in current.title)
			tokens.append(("class:text", f"  Answer: {answer}"))

		show_description = self.show_description and current.description is not None
		if show_description:
			tokens.append(("class:text", f"  Description: {current.description}"))

		if not (self.show_selected or show_description):
			tokens.pop()

		return tokens

	common.InquirerControl._get_choice_tokens = get_choice_tokens


configure_questionary_checkbox_rendering()


def main() -> int:
	if should_show_help(sys.argv[1:]):
		print(render_help(load_help_config()))
		return 0
	if should_show_version(sys.argv[1:]):
		print(f"listkit {get_current_version()}")
		return 0

	parser: argparse.ArgumentParser = argparse.ArgumentParser(
		prog="listkit",
		description="Create Apple Reminders items from a reusable list template.",
		add_help=False,
	)
	parser.add_argument("short_name", nargs="?", help="template short name")
	args: argparse.Namespace = parser.parse_args()

	project_dir: Path = get_project_root()
	config_path: Path = resolve_config_path(project_dir)
	templates_path: Path = resolve_templates_path(project_dir)

	try:
		config: Config = load_config(config_path)
	except ConfigLoadError as error:
		print(f"Error: {error}", file=sys.stderr)
		return 1

	if args.short_name == "config":
		try:
			config_result: str = run_config_editor(config_path, config, prompt_style=build_prompt_style(config.selection_color))
			if config_result == RETURN_TO_LISTKIT_CHOICE:
				config = load_config(config_path)
				return run_listkit_flow(None, config, templates_path)
			return 0
		except ConfigExit:
			return 0
		except ShopAbort:
			print("Aborted.")
			return 130
		except DeliveryError as error:
			print(f"Error: {error}", file=sys.stderr)
			return 1

	return run_listkit_flow(args.short_name, config, templates_path)


def run_listkit_flow(short_name: str | None, config: Config, templates_path: Path) -> int:
	try:
		templates: dict[str, dict[str, Any]] = load_templates(templates_path)
	except TemplateLoadError as error:
		print(f"Error: {error}", file=sys.stderr)
		return 1

	try:
		prompt_style = build_prompt_style(config.selection_color)
		print()
		if short_name is None:
			while True:
				selected_template = select_template(templates, prompt_style=prompt_style)
				if selected_template == CREATE_TEMPLATE_FROM_LIST_CHOICE:
					created_template_path = create_template_from_reminders_list(
						templates_path,
						config,
						prompt_style=prompt_style,
					)
					if created_template_path is not None:
						print()
						print(render_created_template_result(created_template_path))
						templates = load_templates(templates_path)
					continue

				template = selected_template
				break
		else:
			try:
				match: tuple[str, dict[str, Any]] | None = find_template_by_short_name(templates, short_name)
			except TemplateLoadError as error:
				print(f"Error: {error}", file=sys.stderr)
				return 1

			if match is None:
				print(render_missing_template_error(short_name, templates), file=sys.stderr)
				return 1

			_template_id, template = match
			print_selected_template(template["name"], config.selection_color)

		batch_size: float | None = None
		if template_uses_batch_size(template):
			batch_size = prompt_for_batch_size(template, prompt_style=prompt_style)

		include_on_hand: bool = True
		if template_has_on_hand_items(template):
			include_on_hand = prompt_for_include_on_hand(
				config.include_on_hand_default,
				prompt_style=prompt_style,
			)
		print()
	except ShopAbort:
		print("Aborted.")
		return 130

	shopping_list = build_shopping_list(
		template,
		batch_size,
		include_on_hand,
		append_short_name=config.append_short_name,
	)

	color_scheme: ColorScheme = ColorScheme(
		standard_text_color=config.standard_text_color,
		quantity_color=config.quantity_color,
		omitted_ingredient_color=config.omitted_ingredient_color,
	)
	try:
		selected_ingredient_indexes: list[int] = prompt_for_ingredient_items(
			shopping_list,
			prompt_style=prompt_style,
		)
		shopping_list = apply_selected_ingredients(shopping_list, selected_ingredient_indexes)
	except ShopAbort:
		print("Aborted.")
		return 130

	print()
	print(render_final_ingredient_list(without_item_tags(shopping_list), color_scheme=color_scheme))

	try:
		delivery_result: DeliveryResult = AppleRemindersTarget(
			target_selector=lambda target_name, options, omitted_count: select_delivery_target(
				target_name,
				options,
				omitted_count,
				prompt_style=build_prompt_style(config.selection_color),
				default_identifier=config.apple_reminders_list_id,
			),
		).create_list(shopping_list, config)
	except ShopAbort:
		print("Aborted.")
		return 130
	except DeliveryError as error:
		print(f"Error: {error}", file=sys.stderr)
		return 1
	print()
	print(render_delivery_result(delivery_result))

	return 0


def get_project_root() -> Path:
	return Path(__file__).resolve().parents[1]


def get_user_data_dir() -> Path:
	if sys.platform == "darwin":
		return Path.home() / "Library" / "Application Support" / APP_NAME

	return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "easy-reminder-templates"


def should_show_help(arguments: list[str]) -> bool:
	return any(argument in {"-h", "--help"} for argument in arguments)


def should_show_version(arguments: list[str]) -> bool:
	return any(argument in {"-V", "--version"} for argument in arguments)


def load_help_config() -> Config:
	project_config_path: Path = get_project_root() / "config.json"
	user_config_path: Path = get_user_data_dir() / "config.json"
	for config_path in (project_config_path, user_config_path):
		if not config_path.exists():
			continue

		try:
			return load_config(config_path)
		except ConfigLoadError:
			return Config()

	return Config()


def resolve_config_path(project_dir: Path) -> Path:
	project_config_path: Path = project_dir / "config.json"
	if project_config_path.exists():
		return project_config_path

	config_path: Path = get_user_data_dir() / "config.json"
	if not config_path.exists():
		config_path.parent.mkdir(parents=True, exist_ok=True)
		save_config(config_path, Config())

	return config_path


def resolve_templates_path(project_dir: Path) -> Path:
	project_templates_path: Path = project_dir / "templates"
	if project_templates_path.exists():
		return project_templates_path

	user_templates_path: Path = get_user_data_dir() / "templates"
	if not user_templates_path.exists():
		user_templates_path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copytree(Path(__file__).resolve().parent / "default_templates", user_templates_path)

	return user_templates_path


def render_delivery_result(result: DeliveryResult) -> str:
	item_label: str = "item" if len(result.created_items) == 1 else "items"
	omitted_label: str = "item" if len(result.omitted_items) == 1 else "items"
	list_name: str = format_delivery_result_list_name(result.target_name)

	return "\n".join(
		[
			style_instruction(f"{len(result.created_items)} {item_label} added to {list_name}"),
			style_instruction(f"{len(result.omitted_items)} {omitted_label} omitted"),
		]
	)


def format_delivery_result_list_name(target_name: str) -> str:
	if ": " not in target_name:
		return target_name

	return target_name.split(": ", 1)[1]


def render_help(config: Config) -> str:
	colors = ColorScheme(
		standard_text_color=config.standard_text_color,
		quantity_color=config.quantity_color,
		omitted_ingredient_color=config.omitted_ingredient_color,
	)
	lines: list[str] = [
		style_text(APP_NAME, config.selection_color),
		"",
		style_instruction("Create Apple Reminders items from reusable list templates."),
		"",
		style_text("Usage", colors.standard_text_color),
		style_text("-----", colors.standard_text_color),
		f"{style_text('listkit', config.quantity_color)} [template-short-name]",
		f"{style_text('listkit', config.quantity_color)} config",
		f"{style_text('listkit', config.quantity_color)} --version",
		"",
		style_text("Examples", colors.standard_text_color),
		style_text("--------", colors.standard_text_color),
		f"{style_text('listkit', config.quantity_color)}",
		f"{style_text('listkit', config.quantity_color)} chili",
		f"{style_text('listkit', config.quantity_color)} beach",
		f"{style_text('listkit', config.quantity_color)} config",
		f"{style_text('listkit', config.quantity_color)} --version",
		"",
		style_text("Commands", colors.standard_text_color),
		style_text("--------", colors.standard_text_color),
		render_help_row("config", "Open settings", config.quantity_color),
		render_help_row("--version", "Show installed version", config.quantity_color),
		"",
		style_text("Arguments", colors.standard_text_color),
		style_text("---------", colors.standard_text_color),
		render_help_row("template-short-name", "Optional shortcut for a template", config.quantity_color),
	]
	return "\n".join(lines)


def render_help_row(label: str, description: str, color_name: str) -> str:
	padding: str = " " * max(2, 24 - len(label))
	return f"{style_text(label, color_name)}{padding}{description}"


def render_missing_template_error(short_name: str, templates: dict[str, dict[str, Any]]) -> str:
	return "\n".join(
		[
			f'Error: no template found with short name "{short_name}".',
			"",
			"Available templates:",
			*format_available_templates(templates),
			"",
			"Run `listkit` to choose from the menu.",
		]
	)


def format_available_templates(templates: dict[str, dict[str, Any]]) -> list[str]:
	return [f"- {format_available_template(template)}" for template in templates.values()]


def format_available_template(template: dict[str, Any]) -> str:
	short_name: Any = template.get("short_name")
	if isinstance(short_name, str) and short_name != "":
		return f"{template['name']} [{short_name}]"

	return template["name"]


def select_template(templates: dict[str, dict[str, Any]], prompt_style=None) -> dict[str, Any] | str:
	template_options: list[dict[str, Any]] = list(templates.values())
	choices: list[questionary.Choice] = [
		questionary.Choice(
			title=template["name"],
			value=template,
		)
		for template in template_options
	]
	choices.append(create_template_from_list_choice())
	choices.append(abort_choice())

	selection = questionary.select(
		"",
		choices=choices,
		instruction=SELECT_TEMPLATE_INSTRUCTION,
		pointer=">",
		qmark="Select a Template",
		style=prompt_style,
	)
	bind_escape_value(selection, ABORT_CHOICE)
	return require_selection(ask_or_abort(selection))


def create_template_from_reminders_list(
	templates_path: Path,
	config: Config,
	prompt_style=None,
) -> Path | None:
	reminders = AppleRemindersTarget()
	targets: list[DeliveryTargetOption] = reminders.list_targets()
	visible_targets: list[DeliveryTargetOption] = [
		target for target in targets if target.identifier not in config.hidden_apple_reminders_list_ids
	]
	omitted_count: int = len(targets) - len(visible_targets)
	selected_target = select_delivery_target(
		config.apple_reminders_list_name,
		visible_targets,
		omitted_count=omitted_count,
		prompt_style=prompt_style,
		qmark="Choose Source List",
		exit_choice=back_config_choice(),
		instruction_description="Choose the Reminders list to turn into a reusable ListKit template.",
		allow_create_new=False,
		default_identifier=config.apple_reminders_list_id,
	)
	if selected_target == BACK_CONFIG_CHOICE:
		return None

	item_names: list[str] = reminders.list_items(selected_target.identifier)
	template_name: str | None = prompt_for_template_name(selected_target.name, prompt_style=prompt_style)
	if template_name is None:
		return None

	short_name: str | None = prompt_for_template_short_name(template_name, prompt_style=prompt_style)
	if short_name is None:
		return None

	template_path: Path = write_template_from_reminders_list(
		templates_path,
		template_name,
		short_name,
		item_names,
	)
	return template_path


def prompt_for_template_name(default_name: str, prompt_style=None) -> str | None:
	prompt = questionary.text(
		"",
		default=default_name,
		validate=validate_template_name,
		qmark="Template Name",
		instruction=TEMPLATE_NAME_INSTRUCTION,
		style=prompt_style,
	)
	bind_escape_value(prompt, BACK_CONFIG_CHOICE)
	selection = ask_or_abort(prompt)
	if selection == BACK_CONFIG_CHOICE:
		return None

	return require_selection(selection).strip()


def prompt_for_template_short_name(template_name: str, prompt_style=None) -> str | None:
	prompt = questionary.text(
		"",
		default=slugify_template_filename(template_name),
		qmark="Template Short Name",
		instruction=TEMPLATE_SHORT_NAME_INSTRUCTION,
		style=prompt_style,
	)
	bind_escape_value(prompt, BACK_CONFIG_CHOICE)
	selection = ask_or_abort(prompt)
	if selection == BACK_CONFIG_CHOICE:
		return None

	return require_selection(selection).strip()


def write_template_from_reminders_list(
	templates_path: Path,
	template_name: str,
	short_name: str,
	item_names: list[str],
) -> Path:
	lists_path: Path = templates_path / "lists"
	lists_path.mkdir(parents=True, exist_ok=True)
	template_path: Path = next_available_template_path(lists_path, slugify_template_filename(template_name))
	template_data: dict[str, Any] = {
		"schema_version": 1,
		"type": "list",
		"name": template_name,
		"short_name": short_name,
		"default_batch": "",
		"items": [
			{
				"name": item_name,
				"quantity": "",
				"unit": "",
				"always_on_hand": False,
			}
			for item_name in item_names
		],
	}
	template_path.write_text(f"{json.dumps(template_data, indent=2)}\n", encoding="utf-8")
	return template_path


def next_available_template_path(directory: Path, slug: str) -> Path:
	base_slug: str = slug or "template"
	candidate: Path = directory / f"{base_slug}.json"
	index: int = 2
	while candidate.exists():
		candidate = directory / f"{base_slug}-{index}.json"
		index += 1

	return candidate


def slugify_template_filename(value: str) -> str:
	slug: str = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
	return slug or "template"


def render_created_template_result(template_path: Path) -> str:
	return "\n".join(
		[
			style_instruction(f"Template created: {template_path}"),
			style_instruction("Edit the JSON later to add quantities, units, default batch, or on-hand settings."),
			style_instruction("See TEMPLATES.md for the template JSON guide."),
		]
	)


def run_config_editor(config_path: Path, config: Config, prompt_style=None) -> str:
	update_status: UpdateStatus = get_update_status(config)
	while True:
		print()
		selection = questionary.select(
			"",
			choices=[
				questionary.Choice(title="Select Lists", value="reminders_lists"),
				questionary.Choice(title="Set Colors", value="colors"),
				questionary.Choice(title="Set Defaults", value="options"),
				questionary.Choice(title=format_update_menu_title(update_status), value="updates"),
				return_to_listkit_choice(),
				exit_config_choice(),
			],
			instruction=CONFIG_MENU_INSTRUCTION,
			pointer=">",
			qmark="Config",
			style=prompt_style,
		)
		bind_escape_value(selection, EXIT_CONFIG_CHOICE)
		action = require_config_selection(ask_or_abort(selection))
		if action == EXIT_CONFIG_CHOICE:
			return EXIT_CONFIG_CHOICE
		if action == RETURN_TO_LISTKIT_CHOICE:
			return RETURN_TO_LISTKIT_CHOICE

		if action == "reminders_lists":
			config = edit_reminders_list_visibility(config, prompt_style=prompt_style)
			save_config(config_path, config)
			print()
			print("Saved config.json")
			continue

		if action == "colors":
			config = edit_color_settings(config_path, config, prompt_style=prompt_style)
			continue

		if action == "options":
			config = edit_options(config_path, config, prompt_style=prompt_style)
			continue

		if action == "updates":
			config = handle_update_check(config_path, config, update_status, prompt_style=prompt_style)
			update_status = get_update_status(config)
			continue

		print()
		print("Not implemented yet.")


def get_update_status(config: Config) -> UpdateStatus:
	current_version: str = get_current_version()
	try:
		latest_release: ReleaseInfo = fetch_latest_release()
	except UpdateCheckError as error:
		return UpdateStatus(current_version=current_version, error=str(error))

	if not is_newer_version(latest_release.version, current_version):
		return UpdateStatus(current_version=current_version)

	if latest_release.version == config.skipped_update_version:
		return UpdateStatus(current_version=current_version, skipped_release=latest_release)

	return UpdateStatus(current_version=current_version, latest_release=latest_release)


def format_update_menu_title(update_status: UpdateStatus) -> str:
	if update_status.latest_release is None:
		return "Check for Updates"

	return "Check for Updates (1)"


def handle_update_check(
	config_path: Path,
	config: Config,
	update_status: UpdateStatus,
	prompt_style=None,
) -> Config:
	if update_status.error != "":
		print()
		print(f"Update check unavailable: {update_status.error}")
		return config

	if update_status.latest_release is None and update_status.skipped_release is None:
		print()
		print(f"Up to date: {update_status.current_version}")
		return config

	release: ReleaseInfo = update_status.latest_release or update_status.skipped_release
	print()
	print(render_update_changelog(update_status.current_version, release))
	choices: list[questionary.Choice] = [
		questionary.Choice(title=f"Update to v{release.version}", value="show_command"),
		questionary.Choice(title=f"Skip v{release.version}", value="skip_update"),
		back_config_choice(),
	]
	selection = questionary.select(
		"",
		choices=choices,
		instruction=UPDATE_MENU_INSTRUCTION,
		pointer=">",
		qmark="Update Available",
		style=prompt_style,
	)
	bind_escape_value(selection, BACK_CONFIG_CHOICE)
	action = require_config_selection(ask_or_abort(selection))
	if action == BACK_CONFIG_CHOICE:
		return config

	if action == "show_command":
		print()
		print(format_update_command_message(copy_update_command_to_clipboard()))
		raise ConfigExit()

	config = replace(config, skipped_update_version=release.version)
	save_config(config_path, config)
	print()
	print(f"Skipped {release.version}")
	return config


def copy_update_command_to_clipboard() -> bool:
	if sys.platform != "darwin":
		return False

	try:
		subprocess.run(
			["pbcopy"],
			input=UPDATE_COMMAND,
			text=True,
			check=True,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)
	except (OSError, subprocess.CalledProcessError):
		return False

	return True


def format_update_command_message(copied_to_clipboard: bool) -> str:
	lines: list[str] = [
		"Update command:",
		UPDATE_COMMAND,
		"",
	]
	if copied_to_clipboard:
		lines.append("The update command has been copied to your clipboard.")
		lines.append("listkit will exit now. Paste the command into Terminal, and press Enter.")
	else:
		lines.append("listkit will exit now. Paste or type this command into Terminal, and press Enter.")

	return "\n".join(lines)


def render_update_changelog(current_version: str, release: ReleaseInfo) -> str:
	lines: list[str] = [
		"Update Available",
		"----------------",
		f"Current: {current_version}",
		f"Latest: {release.version}",
	]
	if release.name != "":
		lines.append(f"Release: {release.name}")
	if release.url != "":
		lines.append(f"URL: {release.url}")
	lines.extend(["", "Changelog", "---------", release.body.strip() or "No release notes provided."])
	return "\n".join(lines)


def edit_reminders_list_visibility(config: Config, prompt_style=None) -> Config:
	targets: list[DeliveryTargetOption] = AppleRemindersTarget().list_targets()
	hidden_ids: set[str] = set(config.hidden_apple_reminders_list_ids)
	name_counts: Counter[str] = Counter(target.name for target in targets)
	choices: list[questionary.Choice] = [
		questionary.Choice(
			title=format_delivery_target_option(target, show_detail=name_counts[target.name] > 1),
			value=target.identifier,
			checked=target.identifier not in hidden_ids,
		)
		for target in targets
	]
	if len(choices) == 0:
		raise DeliveryError("No Apple Reminders lists were found.")

	selection = questionary.checkbox(
		"",
		choices=choices,
		instruction=CONFIG_LIST_INSTRUCTION,
		pointer=">",
		qmark="Reminder Lists > Select Lists",
		style=prompt_style,
	)
	bind_escape_value(selection, BACK_CONFIG_CHECKBOX_CHOICE)
	visible_ids: set[str] = set(require_selection(ask_or_abort(selection)))
	if visible_ids == set(BACK_CONFIG_CHECKBOX_CHOICE):
		return config

	return replace(
		config,
		hidden_apple_reminders_list_ids=[
			target.identifier
			for target in targets
			if target.identifier not in visible_ids
		],
	)


def edit_color_settings(config_path: Path, config: Config, prompt_style=None) -> Config:
	while True:
		setting = questionary.select(
			"",
			choices=[
				questionary.Choice(
					title=color_setting_choice_title(config, "Standard Text Color", "standard_text_color"),
					value="standard_text_color",
				),
				questionary.Choice(
					title=color_setting_choice_title(config, "Quantity Color", "quantity_color"),
					value="quantity_color",
				),
				questionary.Choice(
					title=color_setting_choice_title(config, "Selection Color", "selection_color"),
					value="selection_color",
				),
				questionary.Choice(
					title=color_setting_choice_title(config, "Omitted Ingredient Color", "omitted_ingredient_color"),
					value="omitted_ingredient_color",
				),
				back_config_choice(),
			],
			instruction=COLOR_MENU_INSTRUCTION,
			pointer=">",
			qmark="Colors",
			style=prompt_style,
		)
		bind_escape_value(setting, BACK_CONFIG_CHOICE)
		setting_name = require_config_selection(ask_or_abort(setting))
		if setting_name == BACK_CONFIG_CHOICE:
			return config

		current_color: str = normalize_config_color(setting_name, getattr(config, setting_name))
		choice_values: list[str] = [CONFIG_COLOR_DEFAULTS[setting_name], *CONFIG_COLOR_OPTIONS]
		if current_color not in choice_values:
			choice_values.insert(0, current_color)
		choices: list[questionary.Choice] = []
		seen_color_values: set[str] = set()
		for color in choice_values:
			if color in seen_color_values:
				continue
			seen_color_values.add(color)
			choices.append(color_choice(color, is_default=color == CONFIG_COLOR_DEFAULTS[setting_name]))
		default_choice: questionary.Choice | None = next(
			(choice for choice in choices if choice.value == current_color),
			None,
		)
		color_selection = questionary.select(
			"",
			choices=choices,
			default=default_choice,
			instruction=format_color_setting_instruction(setting_name),
			pointer=">",
			qmark=format_config_setting_name(setting_name),
			style=prompt_style,
		)
		bind_escape_value(color_selection, BACK_CONFIG_CHOICE)
		selected_color = require_config_selection(ask_or_abort(color_selection))
		if selected_color == BACK_CONFIG_CHOICE:
			continue

		config = replace(config, **{setting_name: selected_color})
		save_config(config_path, config)
		print()
		print("Saved config.json")


def edit_options(config_path: Path, config: Config, prompt_style=None) -> Config:
	while True:
		selection = questionary.select(
			"",
			choices=[
				questionary.Choice(
					title=f"Default Reminder List: {config.apple_reminders_list_name}",
					value="apple_reminders_list",
				),
				questionary.Choice(
					title=f"Include All On-Hand Items: {format_bool_option(config.include_on_hand_default)}",
					value="include_on_hand_default",
				),
				questionary.Choice(
					title=f"Append Short Name: {format_bool_option(config.append_short_name)}",
					value="append_short_name",
				),
				back_config_choice(),
			],
			instruction=OPTIONS_MENU_INSTRUCTION,
			pointer=">",
			qmark="Set Defaults",
			style=prompt_style,
		)
		bind_escape_value(selection, BACK_CONFIG_CHOICE)
		setting_name = require_config_selection(ask_or_abort(selection))
		if setting_name == BACK_CONFIG_CHOICE:
			return config

		if setting_name == "apple_reminders_list":
			config = edit_default_reminders_list(config, prompt_style=prompt_style)
		elif setting_name in {"include_on_hand_default", "append_short_name"}:
			config = edit_bool_option(config, setting_name, prompt_style=prompt_style)

		save_config(config_path, config)
		print()
		print("Saved config.json")


def edit_default_reminders_list(config: Config, prompt_style=None) -> Config:
	targets: list[DeliveryTargetOption] = AppleRemindersTarget().list_targets()
	visible_targets: list[DeliveryTargetOption] = [
		target for target in targets if target.identifier not in config.hidden_apple_reminders_list_ids
	]

	target = select_delivery_target(
		config.apple_reminders_list_name,
		visible_targets,
		omitted_count=len(targets) - len(visible_targets),
		prompt_style=prompt_style,
		qmark="Set Default List",
		exit_choice=back_config_choice(),
		instruction_description="Choose the Reminders list selected by default.",
		default_identifier=config.apple_reminders_list_id,
	)
	if target == BACK_CONFIG_CHOICE:
		return config

	return replace(
		config,
		apple_reminders_list_id=target.identifier,
		apple_reminders_list_name=target.name,
	)


def edit_bool_option(config: Config, setting_name: str, prompt_style=None) -> Config:
	current_value: bool = getattr(config, setting_name)
	choices: list[questionary.Choice] = [
		questionary.Choice(title="Yes", value=True),
		questionary.Choice(title="No", value=False),
		back_config_choice(),
	]
	default_choice: questionary.Choice = choices[0] if current_value else choices[1]
	selection = questionary.select(
		"",
		choices=choices,
		default=default_choice,
		instruction=format_bool_option_instruction(setting_name),
		pointer=">",
		qmark=format_config_setting_name(setting_name),
		style=prompt_style,
	)
	bind_escape_value(selection, BACK_CONFIG_CHOICE)
	value = require_config_selection(ask_or_abort(selection))
	if value == BACK_CONFIG_CHOICE:
		return config

	return replace(config, **{setting_name: value})


def prompt_for_batch_size(recipe: dict[str, Any], prompt_style=None) -> float:
	default_batch: float = float(recipe.get("default_batch", 1))
	default_display: str = format_number(default_batch)
	prompt = questionary.text(
		"",
		default=default_display,
		validate=validate_batch_size,
		qmark="Batch Size",
		instruction=format_prompt_instruction(
			"Enter the batch size for this template.",
			"[ENTER to accept default | ESC to exit | Ctrl-C to quit]",
		),
		style=prompt_style,
	)
	bind_escape_value(prompt, ABORT_CHOICE)

	selection = require_selection(ask_or_abort(prompt)).strip()
	if selection == "":
		return default_batch
	if selection.casefold() in ABORT_COMMANDS:
		raise ShopAbort()
	return float(selection)


def prompt_for_include_on_hand(default: bool, prompt_style=None) -> bool:
	default_choice = questionary.Choice(title="Yes", value=True) if default else questionary.Choice(title="No", value=False)
	other_choice = questionary.Choice(title="No", value=False) if default else questionary.Choice(title="Yes", value=True)
	choices: list[questionary.Choice] = [default_choice, other_choice, abort_choice()]
	selection = questionary.select(
		"",
		choices=choices,
		instruction=format_prompt_instruction(
			"Choose whether on-hand items should start selected.",
			"[↑↓ + ENTER to select | ESC to exit | Ctrl-C to quit]",
		),
		pointer=">",
		qmark="Include All On-Hand Items",
		style=prompt_style,
	)
	bind_escape_value(selection, ABORT_CHOICE)
	return require_selection(ask_or_abort(selection))


def select_delivery_target(
	target_name: str,
	options: list[DeliveryTargetOption],
	omitted_count: int = 0,
	prompt_style=None,
	qmark: str = "Choose Reminder List",
	exit_choice=None,
	instruction_description: str = "Choose where the final items should be added.",
	allow_create_new: bool = True,
	default_identifier: str = "",
) -> DeliveryTargetOption | str:
	print()
	name_counts: Counter[str] = Counter(option.name for option in options)
	choices: list[questionary.Choice] = []
	default_choice: questionary.Choice | None = None
	for option in options:
		choice = questionary.Choice(
			title=format_delivery_target_option(option, show_detail=name_counts[option.name] > 1),
			value=option,
		)
		choices.append(choice)
		if default_choice is None and default_identifier and option.identifier == default_identifier:
			default_choice = choice
		elif default_choice is None and option.name == target_name:
			default_choice = choice

	if allow_create_new:
		choices.append(create_new_list_choice())
	navigation_choice = exit_choice or abort_choice()
	choices.append(navigation_choice)
	selection = questionary.select(
		"",
		choices=choices,
		default=default_choice,
		instruction=format_delivery_target_instruction(
			instruction_description,
			omitted_count,
			escape_action="return" if navigation_choice.value == BACK_CONFIG_CHOICE else "exit",
		),
		pointer=">",
		qmark=qmark,
		style=prompt_style,
	)
	bind_escape_value(selection, navigation_choice.value)
	selected_target: DeliveryTargetOption | str = require_selection(ask_or_abort(selection))
	if selected_target == BACK_CONFIG_CHOICE:
		return BACK_CONFIG_CHOICE

	if not isinstance(selected_target, DeliveryTargetOption):
		return selected_target

	if selected_target.identifier != CREATE_NEW_LIST_IDENTIFIER:
		return selected_target

	return prompt_for_new_delivery_target(prompt_style=prompt_style, escape_value=navigation_choice.value)


def prompt_for_new_delivery_target(prompt_style=None, escape_value: str = ABORT_CHOICE) -> DeliveryTargetOption | str:
	prompt = questionary.text(
		"",
		validate=validate_new_list_name,
		qmark="New Reminder List",
		instruction=format_prompt_instruction(
			"Enter a name for the new Reminders list.",
			f"[ENTER to create | ESC to {escape_control_word(escape_value)} | Ctrl-C to quit]",
		),
		style=prompt_style,
	)
	bind_escape_value(prompt, escape_value)
	selection = ask_or_abort(prompt)
	if selection == BACK_CONFIG_CHOICE:
		return BACK_CONFIG_CHOICE

	list_name: str = require_selection(selection).strip()
	if list_name.casefold() in ABORT_COMMANDS:
		raise ShopAbort()

	return AppleRemindersTarget().create_target(list_name)


def prompt_for_ingredient_items(shopping_list: ShoppingList, prompt_style=None) -> list[int]:
	ordered_items: list[tuple[int, ShoppingListItem]] = order_items_with_on_hand_last(shopping_list.items)
	prefix_width: int = max((len(format_item_prefix(item)) for _index, item in ordered_items), default=0)
	choices: list[questionary.Choice] = [
		questionary.Choice(
			title=format_item(replace(item, tag=None), prefix_width),
			value=index,
			checked=not item.omitted,
		)
		for index, item in ordered_items
	]
	initial_choice: questionary.Choice | None = choices[0] if len(choices) > 0 else None
	if any(item.omitted for _index, item in ordered_items):
		initial_choice = next(
			choice
			for choice, (_index, item) in zip(choices, ordered_items)
			if item.omitted
		)
	selection = questionary.checkbox(
		"",
		choices=choices,
		instruction=INGREDIENT_INSTRUCTION,
		initial_choice=initial_choice,
		pointer=">",
		qmark="Choose Items",
		style=prompt_style,
	)
	bind_escape_value(selection, ABORT_CHOICE)
	selection = ask_or_abort(selection)
	return require_selection(selection)


def render_final_ingredient_list(shopping_list: ShoppingList, color_scheme: ColorScheme) -> str:
	prefix_width: int = max((len(format_item_prefix(item)) for item in shopping_list.included_items), default=0)
	line_width: int = calculate_line_width(shopping_list.included_items, prefix_width)
	lines: list[str] = [
		style_text("Final List", color_scheme.standard_text_color),
		style_text("-" * line_width, color_scheme.standard_text_color),
	]
	for item in shopping_list.included_items:
		lines.append(style_text(f"- {format_item(item, prefix_width, color_scheme)}", color_scheme.standard_text_color))

	return "\n".join(lines)


def without_item_tags(shopping_list: ShoppingList) -> ShoppingList:
	return ShoppingList(
		recipe_name=shopping_list.recipe_name,
		batch_size=shopping_list.batch_size,
		items=[replace(item, tag=None) for item in shopping_list.items],
		included_items=[replace(item, tag=None) for item in shopping_list.included_items],
		omitted_items=[replace(item, tag=None) for item in shopping_list.omitted_items],
	)


def apply_selected_ingredients(
	shopping_list: ShoppingList,
	selected_ingredient_indexes: list[int],
) -> ShoppingList:
	selected_indexes: set[int] = set(selected_ingredient_indexes)
	items: list[ShoppingListItem] = [
		replace(item, omitted=index not in selected_indexes)
		for index, item in order_items_with_on_hand_last(shopping_list.items)
	]

	return ShoppingList(
		recipe_name=shopping_list.recipe_name,
		batch_size=shopping_list.batch_size,
		items=items,
		included_items=[item for item in items if not item.omitted],
		omitted_items=[item for item in items if item.omitted],
	)


def order_items_with_on_hand_last(items: list[ShoppingListItem]) -> list[tuple[int, ShoppingListItem]]:
	return sorted(enumerate(items), key=lambda indexed_item: indexed_item[1].always_on_hand)


def format_delivery_target_option(option: DeliveryTargetOption, show_detail: bool = True) -> str:
	base_label: str = f"{option.name} ({option.item_count})"
	if not show_detail:
		return base_label

	if len(option.sample_items) == 0:
		return base_label

	samples: str = ", ".join(truncate_sample_item(item) for item in option.sample_items[:3])
	return f"{base_label} - {samples}"


def truncate_sample_item(item: str) -> str:
	if len(item) <= TRUNCATED_SAMPLE_LENGTH:
		return item

	return f"{item[:TRUNCATED_SAMPLE_LENGTH]}..."


def format_delivery_target_instruction(description: str, omitted_count: int, escape_action: str = "exit") -> str:
	lines: list[str] = [description]
	if omitted_count > 0:
		lines.append(format_omitted_list_note(omitted_count))
	lines.append(f"[↑↓ + ENTER to select | ESC to {escape_action} | Ctrl-C to quit]")
	return "\n" + "\n".join(lines) + "\n"


def format_omitted_list_note(omitted_count: int) -> str:
	list_label: str = "list" if omitted_count == 1 else "lists"
	return f"{omitted_count} {list_label} omitted per config.json"


def format_bool_option_instruction(setting_name: str) -> str:
	descriptions: dict[str, str] = {
		"include_on_hand_default": "Choose whether on-hand items are selected by default.",
		"append_short_name": "Choose whether template short names are appended to reminder items.",
	}
	return format_prompt_instruction(
		descriptions.get(setting_name, "Choose the default value for this setting."),
		"[↑↓ + ENTER to select | ESC to return | Ctrl-C to quit]",
	)


def escape_control_word(escape_value: str) -> str:
	if escape_value == BACK_CONFIG_CHOICE:
		return "return"

	return "exit"


def abort_choice():
	return questionary.Choice(
		title=[("class:app-action", ABORT_TITLE)],
		value=ABORT_CHOICE,
	)


def create_new_list_choice():
	return questionary.Choice(
		title=[("class:app-action", CREATE_NEW_LIST_TITLE)],
		value=DeliveryTargetOption(
			identifier=CREATE_NEW_LIST_IDENTIFIER,
			name=CREATE_NEW_LIST_TITLE,
			source="",
			item_count=0,
			sample_items=[],
		),
	)


def create_template_from_list_choice():
	return questionary.Choice(
		title=[("class:app-action", CREATE_TEMPLATE_FROM_LIST_TITLE)],
		value=CREATE_TEMPLATE_FROM_LIST_CHOICE,
	)


def exit_config_choice():
	return questionary.Choice(title=[("class:app-action", EXIT_CONFIG_TITLE)], value=EXIT_CONFIG_CHOICE)


def return_to_listkit_choice():
	return questionary.Choice(title=[("class:app-action", RETURN_TO_LISTKIT_TITLE)], value=RETURN_TO_LISTKIT_CHOICE)


def back_config_choice():
	return questionary.Choice(title=[("class:app-action", BACK_CONFIG_TITLE)], value=BACK_CONFIG_CHOICE)


def color_choice(color_name: str, is_default: bool = False):
	label: str = f"{color_name} (default)" if is_default else color_name
	style: str = color_title_style(color_name)
	return questionary.Choice(title=[(style, label)], value=color_name)


def color_title_style(color_name: str) -> str:
	if color_name in NAMED_COLORS:
		return f"class:color-{color_name}"

	style: str = prompt_color_style(color_name)
	if style != "":
		return style

	return "class:text"


def normalize_config_color(setting_name: str, color_name: str) -> str:
	if color_name == "default":
		return CONFIG_COLOR_DEFAULTS[setting_name]

	return normalize_color(color_name, CONFIG_COLOR_DEFAULTS[setting_name])


def format_config_color_value(config: Config, setting_name: str) -> str:
	color_name: str = normalize_config_color(setting_name, getattr(config, setting_name))
	default_color: str = CONFIG_COLOR_DEFAULTS[setting_name]
	if color_name == default_color:
		return f"{color_name} (default)"

	return color_name


def format_config_color_menu_value(config: Config, setting_name: str) -> str:
	return normalize_config_color(setting_name, getattr(config, setting_name))


def color_setting_choice_title(config: Config, label: str, setting_name: str) -> list[tuple[str, str]]:
	color_value: str = format_config_color_menu_value(config, setting_name)
	return [
		("class:text", f"{label}: "),
		(color_title_style(color_value), color_value),
	]


def bind_escape_value(prompt, value) -> None:
	if not hasattr(prompt, "application"):
		return

	key_bindings = prompt.application.key_bindings
	if hasattr(key_bindings, "add"):
		registry = key_bindings
	else:
		registry = KeyBindings()
		prompt.application.key_bindings = merge_key_bindings([key_bindings, registry])

	@registry.add(Keys.Escape, eager=True)
	def _(event):
		event.app.exit(result=value)


def format_config_setting_name(setting_name: str) -> str:
	return setting_name.replace("_", " ").title()


def format_bool_option(value: bool) -> str:
	return "Yes" if value else "No"


def validate_new_list_name(value: str) -> bool | str:
	if value.strip() == "":
		return "Enter a list name."

	return True


def validate_template_name(value: str) -> bool | str:
	if value.strip() == "":
		return "Enter a template name."

	return True


def format_color_setting_instruction(setting_name: str) -> str:
	return f"\n{COLOR_SETTING_INSTRUCTIONS[setting_name]}\n{COLOR_PICKER_HEX_NOTE}\n{COLOR_PICKER_CONTROLS}\n"


def style_instruction(value: str) -> str:
	return f"\033[90m{value}\033[0m"


def print_selected_template(template_name: str, color_name: str = Config.selection_color) -> None:
	color: str = terminal_color_code(normalize_color(color_name, Config.selection_color))
	if color == "":
		print(f"Select a Template  {template_name}")
		return

	print(f"Select a Template  {color}{template_name}\033[0m")


def validate_batch_size(selection: str) -> bool | str:
	selection = selection.strip()
	if selection == "":
		return True

	if selection.casefold() in ABORT_COMMANDS:
		return True

	try:
		batch_size: float = float(selection)
	except ValueError:
		return "Enter a positive number."

	if batch_size <= 0:
		return "Enter a positive number."

	return True


def build_prompt_style(color_name: str):
	color: str = prompt_color_style(color_name)
	styles: dict[str, str] = {
		"abort": "ansired noreverse noinherit",
		"app-action": "#d56aa0 bold noreverse noinherit",
		"selected": f"{color} noreverse noinherit" if color != "" else "ansiyellow noreverse noinherit",
		"answer": f"{color} noinherit" if color != "" else "ansiyellow noinherit",
		"instruction": "ansibrightblack",
		"qmark": "bold",
		"question": "bold",
		"highlighted": "noreverse noinherit",
	}
	for color_option in NAMED_COLORS:
		ansi_color: str = prompt_color_style(color_option)
		if ansi_color != "":
			styles[f"color-{color_option}"] = f"{ansi_color} noinherit"
	if color != "":
		styles["pointer"] = f"{color} bold noinherit"

	return questionary.Style.from_dict(styles)


def require_selection(selection):
	if selection is None or selection == ABORT_CHOICE:
		raise ShopAbort()

	return selection


def require_config_selection(selection):
	if selection is None:
		raise ShopAbort()

	return selection


def ask_or_abort(prompt):
	try:
		return prompt.ask()
	except (KeyboardInterrupt, EOFError) as error:
		raise ShopAbort() from error


if __name__ == "__main__":
	raise SystemExit(main())
