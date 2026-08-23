from __future__ import annotations

import json
import re
import subprocess
import webbrowser
from dataclasses import replace
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.worker import Worker, WorkerState
from textual.widgets import Input, Label, ListItem, ListView, ProgressBar, Static

from recipe_shopper.colors import HEX_COLOR_PATTERN, normalize_color
from recipe_shopper.config import Config, save_config
from recipe_shopper.delivery import AppleRemindersTarget, DeliveryError, DeliveryResult, DeliveryTargetOption
from recipe_shopper.formatter import (
	ColorScheme,
	ShoppingList,
	ShoppingListItem,
	build_shopping_list,
	format_item,
	format_item_prefix,
)
from recipe_shopper.templates import (
	TemplateLoadError,
	TemplateMap,
	find_template_by_short_name,
	load_templates,
	template_has_on_hand_items,
	template_uses_batch_size,
)
from recipe_shopper.updates import (
	GITHUB_ISSUES_URL,
	ReleaseInfo,
	UpdateCheckError,
	UpdateResult,
	fetch_latest_release,
	get_current_version,
	is_newer_version,
	run_package_update,
)


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
TEXTUAL_COLOR_STYLES: dict[str, str] = {
	"black": "#666666",
	"red": "#ff3b30",
	"green": "#34c759",
	"yellow": "#ffcc00",
	"blue": "#37b7f0",
	"magenta": "#ff2dcb",
	"cyan": "#32ade6",
	"white": "#f2f0ea",
	"grey": "#777777",
}
CONFIG_COLOR_DEFAULTS: dict[str, str] = {
	"standard_text_color": Config.standard_text_color,
	"quantity_color": Config.quantity_color,
	"selection_color": Config.selection_color,
	"omitted_ingredient_color": Config.omitted_ingredient_color,
}
RELAUNCH_RESULT_CODE: int = 30
COLOR_SETTING_LABELS: dict[str, str] = {
	"standard_text_color": "Standard Text Color",
	"quantity_color": "Quantity Color",
	"selection_color": "Selection Color",
	"omitted_ingredient_color": "Omitted Ingredient Color",
}
SORT_ORDER_LABELS: dict[str, str] = {
	"name_asc": "A-Z",
	"name_desc": "Z-A",
	"most_frequently_used": "Most Frequently Used",
	"item_count_asc": "Item Count Ascending",
	"item_count_desc": "Item Count Descending",
}
TEMPLATE_SORT_ORDER_OPTIONS: tuple[str, ...] = (
	"name_asc",
	"name_desc",
	"most_frequently_used",
)
REMINDERS_LIST_SORT_ORDER_OPTIONS: tuple[str, ...] = (
	"name_asc",
	"name_desc",
	"most_frequently_used",
	"item_count_asc",
	"item_count_desc",
)
LISTKIT_BANNER: str = """\
 _     _     _   _  ___ _   
| |   (_)___| |_| |/ (_) |_ 
| |   | / __| __| ' /| | __|
| |___| \\__ \\ |_| . \\| | |_ 
|_____|_|___/\\__|_|\\_\\_|\\__|
"""
MAIN_MENU_INSTRUCTIONS: str = (
	"ListKit helps you turn recipes, packing lists, regular shopping trips, and other repeatable tasks into reusable "
	"templates. Choose Add from Template to start from an example or make your own template from an existing Apple "
	"Reminders list. For details, see the documentation: [link]."
)


class OptionItem(ListItem):
	def __init__(self, label: str, value: object, selectable: bool = True, markup: bool = False) -> None:
		super().__init__(Label(label, markup=markup), disabled=not selectable)
		self.label_text = label
		self.selectable = selectable
		self.value = value
		self.markup = markup

	def set_label(self, label: str) -> None:
		self.label_text = label
		self.query_one(Label).update(label)


class WrappingListView(ListView):
	def action_cursor_down(self) -> None:
		self.move_cursor(1)

	def action_cursor_up(self) -> None:
		self.move_cursor(-1)

	def move_cursor(self, direction: int) -> None:
		if len(self.children) == 0:
			return
		start = self.index if self.index is not None else 0
		for offset in range(1, len(self.children) + 1):
			index = (start + direction * offset) % len(self.children)
			item = self.children[index]
			if isinstance(item, OptionItem) and item.selectable and item.label_text.strip():
				self.index = index
				return


class IngredientListView(WrappingListView):
	BINDINGS = [
		("up", "cursor_up", "Cursor up"),
		("down", "cursor_down", "Cursor down"),
		("space", "toggle_cursor_item", "Toggle item"),
		("enter", "continue_items", "Continue"),
	]

	def action_toggle_cursor_item(self) -> None:
		self.app.toggle_current_ingredient(self.index)  # type: ignore[attr-defined]

	def action_continue_items(self) -> None:
		self.app.continue_from_ingredients(self.index)  # type: ignore[attr-defined]


class ConfigListVisibilityView(WrappingListView):
	BINDINGS = [
		("up", "cursor_up", "Cursor up"),
		("down", "cursor_down", "Cursor down"),
		("space", "toggle_cursor_item", "Toggle list"),
		("enter", "save_lists", "Save"),
	]

	def action_toggle_cursor_item(self) -> None:
		self.app.toggle_current_config_list(self.index)  # type: ignore[attr-defined]

	def action_save_lists(self) -> None:
		self.app.save_config_list_visibility()  # type: ignore[attr-defined]


class UpdateStatus:
	def __init__(
		self,
		current_version: str,
		latest_release: ReleaseInfo | None = None,
		skipped_release: ReleaseInfo | None = None,
		error: str = "",
	) -> None:
		self.current_version = current_version
		self.latest_release = latest_release
		self.skipped_release = skipped_release
		self.error = error


class ListKitApp(App[int]):
	CSS = """
	Screen {
		background: #050505;
		color: #f2f0ea;
	}

	#shell {
		height: 1fr;
		padding: 0 1;
	}

	#context {
		height: auto;
		margin-bottom: 1;
		color: #37b7f0;
	}

	#title {
		text-style: bold;
		color: #ff4b1f;
		margin-bottom: 0;
	}

	#body {
		height: 1fr;
	}

	#footer-note {
		height: auto;
		color: #ff4b1f;
		margin-top: 1;
	}

	ListView {
		height: auto;
		max-height: 24;
		width: 100%;
		background: #050505;
	}

	ListView:focus > ListItem.--highlight {
		background: #050505;
		color: #ff4b1f;
		text-style: bold;
	}

	Input {
		width: 40;
		height: 1;
		padding: 0;
		border: none;
		background: #050505;
		margin-bottom: 1;
	}

	Input:focus {
		border: none;
		background: #050505;
	}

	.item-row {
		height: auto;
	}

	.summary {
		margin-top: 1;
	}

	.menu-spacer {
		height: 1;
	}
	"""

	BINDINGS = [
		("enter", "continue", "Continue"),
		("escape", "back", "Back"),
		("ctrl+c", "quit_app", "Quit"),
	]

	def __init__(
		self,
		config: Config,
		templates_path: Path,
		short_name: str | None = None,
		config_path: Path | None = None,
		start_config: bool = False,
	) -> None:
		super().__init__()
		self.config = config
		self.config_path = config_path
		self.templates_path = templates_path
		self.short_name = short_name
		self.start_config = start_config
		self.templates: TemplateMap = {}
		self.template: dict[str, Any] | None = None
		self.template_id: str = ""
		self.batch_size: float | None = None
		self.include_on_hand: bool = True
		self.shopping_list: ShoppingList | None = None
		self.selected_item_indexes: set[int] = set()
		self.delivery_target: DeliveryTargetOption | None = None
		self.result_code: int = 0
		self.view_name: str = "main"
		self.items_cursor_value: object | None = None
		self.items_cursor_index: int = 0
		self.config_visible_list_ids: set[str] = set()
		self.config_list_targets: list[DeliveryTargetOption] = []
		self.config_color_setting: str = ""
		self.update_status: UpdateStatus | None = None
		self.update_check_requested: bool = False
		self.update_release: ReleaseInfo | None = None
		self.update_result: UpdateResult | None = None
		self.update_worker: Worker | None = None
		self.template_source_target: DeliveryTargetOption | None = None
		self.template_item_names: list[str] = []
		self.template_name: str = ""

	def compose(self) -> ComposeResult:
		with Container(id="shell"):
			yield Static("", id="context")
			yield Static("", id="title")
			with Vertical(id="body"):
				pass
			yield Static("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]", id="footer-note")

	def on_mount(self) -> None:
		self.title = "ListKit"
		try:
			self.templates = load_templates(self.templates_path)
		except TemplateLoadError as error:
			if not is_empty_templates_error(error):
				self.show_error(str(error))
				return
			self.templates = {}
			self.ensure_template_folders()

		if self.start_config:
			self.show_config_menu()
			return

		if self.short_name:
			self.start_short_name_flow(self.short_name)
			return

		self.show_main_menu()

	def show_main_menu(self) -> None:
		self.view_name = "main"
		self.set_header(
			f"{LISTKIT_BANNER}Reusable templates for Apple Reminders.\n[#777777]Version {get_current_version()}[/]",
			MAIN_MENU_INSTRUCTIONS,
			markup=True,
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC exit | Ctrl-C quit]")
		menu = self.build_list(
			[
				("Add from Template", "create_list"),
				("Create Template from List", "create_template"),
				("Settings", "config"),
				("Help", "help"),
				("⏻ Quit", "exit"),
			]
		)
		self.replace_body(Static("", classes="menu-spacer"), menu)
		menu.focus()

	def show_template_menu(self, warning: str = "") -> None:
		self.view_name = "template"
		try:
			self.templates = load_templates(self.templates_path)
		except TemplateLoadError as error:
			if not is_empty_templates_error(error):
				self.show_error(str(error))
				return
			self.templates = {}
			warning = "No templates found. Create one from a Reminders list or open the templates folder."
			self.ensure_template_folders()
		self.set_header(
			"Select Template",
			warning or "Choose a saved template. ListKit will let you review and edit the items before adding them to Reminders.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		options: list[tuple[str, object]] = [
			(template["name"], ("template", template_id))
			for template_id, template in sort_templates(
				self.templates,
				self.config.template_sort_order,
				self.config.template_usage_counts,
			)
		]
		if len(options) == 0:
			options.extend(
				[
					("Create Template from List", "create_template"),
					("Open Templates Folder", "help:open_templates"),
				]
			)
		options.append(("↩ Back", "back"))
		menu = self.build_list(options)
		self.replace_body(menu)
		menu.focus()

	def show_create_template_source_screen(self) -> None:
		self.view_name = "template_source"
		self.set_header("Create Template from List", "Choose the Reminders list to turn into a reusable ListKit template.")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		try:
			targets = AppleRemindersTarget().list_targets()
		except DeliveryError as error:
			self.show_error(str(error))
			return

		visible_targets = [
			target for target in targets if target.identifier not in self.config.hidden_apple_reminders_list_ids
		]
		if len(visible_targets) == 0:
			self.show_error("No visible Reminders lists are available.")
			return

		name_counts: dict[str, int] = {}
		for target in visible_targets:
			name_counts[target.name] = name_counts.get(target.name, 0) + 1

		options: list[tuple[str, object]] = [
			(format_target_label(target, name_counts[target.name] > 1), ("template_source", target))
			for target in sorted(visible_targets, key=lambda value: value.name.casefold())
		]
		options.append(("↩ Back", "back"))
		menu = self.build_list(options, default_value=self.config.apple_reminders_list_id or self.config.apple_reminders_list_name)
		self.replace_body(menu)
		menu.focus()

	def show_template_name_screen(self) -> None:
		assert self.template_source_target is not None
		self.view_name = "template_name"
		self.set_header("Template Name", "Enter the display name for this template.")
		self.set_footer("[ENTER continue | ESC back | Ctrl-C quit]")
		self.replace_body(Input(value=self.template_source_target.name, placeholder="Template name", id="template-name-input"))
		self.query_one("#template-name-input", Input).focus()

	def show_template_short_name_screen(self) -> None:
		self.view_name = "template_short_name"
		self.set_header("Template Short Name", "Enter the short name used by listkit <short-name>.")
		self.set_footer("[ENTER create | ESC back | Ctrl-C quit]")
		self.replace_body(Input(value=slugify_template_filename(self.template_name), placeholder="Short name", id="template-short-name-input"))
		self.query_one("#template-short-name-input", Input).focus()

	def submit_template_source(self, target: DeliveryTargetOption) -> None:
		self.template_source_target = target
		try:
			self.template_item_names = AppleRemindersTarget().list_items(target.identifier)
		except DeliveryError as error:
			self.show_error(str(error))
			return
		self.show_template_name_screen()

	def submit_template_name(self, value: str) -> None:
		template_name = value.strip()
		if template_name == "":
			self.show_template_name_screen()
			self.query_one("#context", Static).update("Template name cannot be blank.")
			return
		self.template_name = template_name
		self.show_template_short_name_screen()

	def submit_template_short_name(self, value: str) -> None:
		short_name = value.strip()
		if short_name == "":
			self.show_template_short_name_screen()
			self.query_one("#context", Static).update("Short name cannot be blank.")
			return
		template_path = write_template_from_reminders_list(
			self.templates_path,
			self.template_name,
			short_name,
			self.template_item_names,
		)
		try:
			self.templates = load_templates(self.templates_path)
		except TemplateLoadError as error:
			self.show_error(str(error))
			return
		self.show_created_template_result(template_path)

	def start_short_name_flow(self, short_name: str) -> None:
		try:
			match = find_template_by_short_name(self.templates, short_name)
		except TemplateLoadError as error:
			self.show_error(str(error))
			return

		if match is None:
			self.short_name = None
			self.show_template_menu(f'Template "{short_name}" was not found. Choose a template below, or go back to the main menu.')
			return

		template_id, template = match
		self.start_template(template, template_id)

	def start_template(self, template: dict[str, Any], template_id: str = "") -> None:
		valid_template = template_with_valid_items(template)
		if valid_template is None:
			self.short_name = None
			self.show_template_menu(
				f'Template "{template["name"]}" does not have any named items yet. Add at least one item to its JSON file, then try again.'
			)
			return

		self.template = valid_template
		self.template_id = template_id
		self.batch_size = None
		self.include_on_hand = True
		self.shopping_list = None
		self.selected_item_indexes = set()

		if template_uses_batch_size(valid_template):
			self.show_batch_screen()
			return

		self.show_on_hand_screen()

	def show_batch_screen(self) -> None:
		assert self.template is not None
		self.view_name = "batch"
		default_batch = str(self.template.get("default_batch", ""))
		self.set_header(
			"Number of Batches",
			"This template looks like a recipe. ListKit can adjust quantities while assembling the ingredients. How many batches would you like to make?",
		)
		self.set_footer("[ENTER continue | ESC back | Ctrl-C quit]")
		self.replace_body(Input(value=default_batch, placeholder="Batch size", id="batch-input"))
		self.query_one("#batch-input", Input).focus()

	def show_on_hand_screen(self) -> None:
		assert self.template is not None
		if not template_has_on_hand_items(self.template):
			self.build_items()
			return

		self.view_name = "on_hand"
		self.set_header(
			"Start with On-Hand Items Selected?",
			"Some items in this template are marked as usually on hand. Should ListKit start with those items checked? You can still review and change the list before sending it to Reminders.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		default = self.config.include_on_hand_default
		options = [("Yes", True), ("No", False)] if default else [("No", False), ("Yes", True)]
		menu = self.build_list(options)
		self.replace_body(menu)
		menu.focus()

	def build_items(self) -> None:
		assert self.template is not None
		self.shopping_list = build_shopping_list(
			self.template,
			self.batch_size,
			self.include_on_hand,
			append_short_name=self.config.append_short_name,
		)
		self.selected_item_indexes = {
			index
			for index, item in enumerate(self.shopping_list.items)
			if not item.omitted
		}
		self.show_items_screen()

	def show_items_screen(self) -> None:
		assert self.shopping_list is not None
		self.view_name = "items"
		self.set_header(
			"Review Items",
			"Select the items you want to add to Reminders. You'll choose the target Reminders list in the next step.",
		)
		self.set_footer("[↑↓ select | SPACE toggle | ENTER continue | ESC back | Ctrl-C quit]")
		ordered_items = order_items_with_on_hand_last(self.shopping_list.items)
		prefix_width = max((len(format_item_prefix(item)) for _index, item in ordered_items), default=0)
		options: list[tuple[str, object]] = []
		for index, item in ordered_items:
			options.append((self.format_ingredient_option(index, item, prefix_width), ("toggle_item", index)))
		default_value = self.items_cursor_value
		if default_value is None:
			default_value = ("toggle_item", ordered_items[0][0]) if ordered_items else None
		item_list = self.build_list(options, default_value=default_value, default_index=self.items_cursor_index, list_type=IngredientListView)
		self.replace_body(item_list)
		item_list.focus()

	def show_target_screen(self) -> None:
		self.view_name = "target"
		self.set_header("Choose Destination", "Select the Reminders list where ListKit should add the selected items.")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		try:
			targets = AppleRemindersTarget().list_targets()
		except DeliveryError as error:
			self.show_error(str(error))
			return

		visible_targets = [
			target for target in targets if target.identifier not in self.config.hidden_apple_reminders_list_ids
		]
		if len(visible_targets) == 0:
			self.show_new_list_screen("No visible Reminders lists are available. Enter a name for a new list to continue.")
			return

		name_counts: dict[str, int] = {}
		for target in visible_targets:
			name_counts[target.name] = name_counts.get(target.name, 0) + 1

		options: list[tuple[str, object]] = [
			(format_target_label(target, name_counts[target.name] > 1), target)
			for target in sort_reminders_targets(
				visible_targets,
				self.config.reminders_list_sort_order,
				self.config.reminders_list_usage_counts,
			)
		]
		options.append(("Create New List", "create_target"))
		menu = self.build_list(options, default_value=self.config.apple_reminders_list_id or self.config.apple_reminders_list_name)
		self.replace_body(menu)
		menu.focus()

	def show_new_list_screen(self, description: str = "Enter a name for the new Reminders list.") -> None:
		self.view_name = "new_list"
		self.set_header("New Reminder List", description)
		self.set_footer("[ENTER create | ESC back | Ctrl-C quit]")
		self.replace_body(Input(placeholder="List name", id="new-list-input"))
		self.query_one("#new-list-input", Input).focus()

	def create_target(self, list_name: str) -> None:
		if list_name.strip() == "":
			self.show_new_list_screen("List name cannot be blank.")
			return
		try:
			self.delivery_target = AppleRemindersTarget().create_target(list_name.strip())
		except DeliveryError as error:
			self.show_error(str(error))
			return
		self.create_reminders()

	def create_reminders(self) -> None:
		assert self.shopping_list is not None
		assert self.delivery_target is not None
		target_config = replace(
			self.config,
			apple_reminders_list_id=self.delivery_target.identifier,
			apple_reminders_list_name=self.delivery_target.name,
		)
		try:
			result = AppleRemindersTarget().create_list(self.shopping_list, target_config)
		except DeliveryError as error:
			self.show_error(str(error))
			return
		self.record_template_usage()
		self.record_reminders_list_usage(self.delivery_target)
		self.save_current_config()
		self.show_result(result)

	def show_result(self, result: DeliveryResult) -> None:
		self.view_name = "result"
		created_label = "item" if len(result.created_items) == 1 else "items"
		self.set_header(f"{len(result.created_items)} {created_label} added to {result.target_name}", "")
		self.set_footer("[ENTER create another | ESC main menu | Ctrl-C quit]")
		self.replace_body(
			Static(
				render_created_items_summary(result.created_items),
				classes="summary",
			),
		)

	def show_created_template_result(self, template_path: Path) -> None:
		self.view_name = "result"
		self.set_header("Template Created", "The Reminders list is now available as a ListKit template.")
		self.set_footer("[ENTER continue | ESC back | Ctrl-C quit]")
		self.replace_body(
			Static(
				f"Template created: {template_path}\n\n"
				"Edit the JSON later to add quantities, units, default batch, or on-hand settings.\n\n"
				"See TEMPLATES.md for the template JSON guide.\n\n"
				"Press ENTER to return to the list selection screen."
			),
		)

	def show_error(self, message: str) -> None:
		self.view_name = "error"
		self.set_header("Error", "ListKit could not continue.")
		self.set_footer("[ENTER exit | Ctrl-C quit]")
		self.result_code = 1
		self.replace_body(
			Static(escape(message)),
		)

	def show_help(self) -> None:
		self.view_name = "help"
		self.set_header(
			"Help",
			"Create reusable templates from Reminders lists, then add selected items back to Reminders whenever you need them.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				("Open Templates Folder", "help:open_templates"),
				("Open Documentation", "help:open_docs"),
				("↩ Back", "back"),
			]
		)
		self.replace_body(
			Static(
				"[bold]Short Names[/]\n"
				"Run listkit <short-name> to jump straight into a template. Short names are set in each template JSON file.\n\n"
				"[bold]Template Files[/]\n"
				"Templates are stored as JSON. You can edit quantities, units, default batch size, on-hand items, and short names directly. To remove unwanted templates, delete them from the templates folder.\n\n"
				"[bold]Documentation[/]\n"
				"For template JSON details and examples, open TEMPLATES.md."
			),
			Static("", classes="menu-spacer"),
			menu,
		)
		menu.focus()

	def show_config_menu(self) -> None:
		self.view_name = "config"
		if self.update_status is None:
			self.update_status = self.get_update_status()
		self.set_header("Settings", format_settings_context(self.update_status))
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		update_title = format_update_menu_label(self.update_status, self.update_check_requested)
		menu = self.build_list(
			[
				("Manage Lists", "config:lists"),
				("Sort Order", "config:sort_order"),
				("Usage History", "config:usage_history"),
				("Colors", "config:colors"),
				("Defaults", "config:defaults"),
				(update_title, "config:updates"),
				("↩ Back", "config:return"),
			]
		)
		self.replace_body(menu)
		menu.focus()

	def show_config_sort_order_menu(self) -> None:
		self.view_name = "config_sort_order"
		self.set_header(
			"Sort Order",
			"Choose how templates and Reminders lists are ordered when ListKit shows a picker.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				(f"Templates: {format_sort_order_label(self.config.template_sort_order)}", "config:template_sort_order"),
				(f"Reminders Lists: {format_sort_order_label(self.config.reminders_list_sort_order)}", "config:reminders_list_sort_order"),
				("↩ Back", "config:sort_order_back"),
			]
		)
		self.replace_body(menu)
		menu.focus()

	def show_config_sort_order_picker(self, setting_name: str) -> None:
		self.view_name = f"config_sort:{setting_name}"
		if setting_name == "template_sort_order":
			self.set_header(
				"Template Order",
				"Choose how saved templates are ordered when selecting what to add.",
			)
		else:
			self.set_header(
				"Reminders List Order",
				"Choose how Reminders lists are ordered when selecting a destination or choosing which lists are visible.",
			)
		self.set_footer("[↑↓ select | ENTER save | ESC back | Ctrl-C quit]")
		current_value = getattr(self.config, setting_name)
		sort_orders = (
			TEMPLATE_SORT_ORDER_OPTIONS
			if setting_name == "template_sort_order"
			else REMINDERS_LIST_SORT_ORDER_OPTIONS
		)
		options = [
			(format_sort_order_label(sort_order), f"config:set_sort:{setting_name}:{sort_order}")
			for sort_order in sort_orders
		]
		options.append(("↩ Back", "config:sort_picker_back"))
		menu = self.build_list(options, default_value=f"config:set_sort:{setting_name}:{current_value}")
		self.replace_body(menu)
		menu.focus()

	def save_config_sort_order(self, setting_name: str, sort_order: str) -> None:
		if setting_name == "template_sort_order":
			self.config = replace(self.config, template_sort_order=sort_order)
		elif setting_name == "reminders_list_sort_order":
			self.config = replace(self.config, reminders_list_sort_order=sort_order)
		self.save_current_config()
		self.show_config_sort_order_menu()

	def show_usage_history_menu(self) -> None:
		self.view_name = "config_usage_history"
		self.set_header(
			"Usage History",
			"Review or reset the local counts used by Most Frequently Used sort order.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				("Template Usage", "config:template_usage"),
				("Reminders List Usage", "config:list_usage"),
				("↩ Back", "config:usage_history_back"),
			]
		)
		self.replace_body(menu)
		menu.focus()

	def show_template_usage_history(self) -> None:
		self.view_name = "config_template_usage"
		self.set_header(
			"Template Usage",
			"These local counts are used by Template Order: Most Frequently Used. To manually adjust values, open config.json.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		options: list[tuple[str, object] | tuple[str, object, bool]] = [
			(label, "config:usage_heading", False)
			for label in format_template_usage_rows(self.templates, self.config.template_usage_counts)
		]
		options.extend(
			[
				("", "config:usage_spacer", False),
				("Open config.json", "config:open_config"),
				("Reset All to Zero", "config:confirm_reset_template_usage"),
				("↩ Back", "config:usage_picker_back"),
			]
		)
		menu = self.build_list(options, default_value="config:open_config")
		self.replace_body(menu)
		menu.focus()

	def show_list_usage_history(self) -> None:
		self.view_name = "config_list_usage"
		self.set_header(
			"Reminders List Usage",
			"These local counts are used by Reminders List Order: Most Frequently Used. To manually adjust values, open config.json.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		try:
			targets = AppleRemindersTarget().list_targets()
		except DeliveryError as error:
			self.show_error(str(error))
			return
		options: list[tuple[str, object] | tuple[str, object, bool]] = [
			(label, "config:usage_heading", False)
			for label in format_reminders_list_usage_rows(targets, self.config.reminders_list_usage_counts)
		]
		options.extend(
			[
				("", "config:usage_spacer", False),
				("Open config.json", "config:open_config"),
				("Reset All to Zero", "config:confirm_reset_list_usage"),
				("↩ Back", "config:usage_picker_back"),
			]
		)
		menu = self.build_list(options, default_value="config:open_config")
		self.replace_body(menu)
		menu.focus()

	def show_reset_usage_confirmation(self, usage_kind: str) -> None:
		self.view_name = f"config_confirm_reset:{usage_kind}"
		title = "Reset Template Usage?" if usage_kind == "template" else "Reset Reminders List Usage?"
		self.set_header(
			title,
			"This clears local usage counts only. It does not change templates or Reminders lists. To manually adjust values, open config.json.",
		)
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				("Confirm Reset", f"config:reset_usage:{usage_kind}"),
				("Cancel", f"config:reset_usage_back:{usage_kind}"),
			]
		)
		self.replace_body(menu)
		menu.focus()

	def reset_usage_history(self, usage_kind: str) -> None:
		if usage_kind == "template":
			self.config = replace(self.config, template_usage_counts={})
			self.save_current_config()
			self.show_template_usage_history()
		else:
			self.config = replace(self.config, reminders_list_usage_counts={})
			self.save_current_config()
			self.show_list_usage_history()

	def return_from_reset_usage_confirmation(self, usage_kind: str) -> None:
		if usage_kind == "template":
			self.show_template_usage_history()
		else:
			self.show_list_usage_history()

	def show_config_list_visibility(self) -> None:
		self.view_name = "config_lists"
		self.set_header("Manage Lists", "Choose which Reminders lists appear when selecting a destination for new items.")
		self.set_footer("[↑↓ select | SPACE toggle | ENTER save | ESC back | Ctrl-C quit]")
		try:
			self.config_list_targets = AppleRemindersTarget().list_targets()
		except DeliveryError as error:
			self.show_error(str(error))
			return

		if len(self.config_list_targets) == 0:
			self.show_error("No Apple Reminders lists were found.")
			return

		hidden_ids = set(self.config.hidden_apple_reminders_list_ids)
		self.config_visible_list_ids = {
			target.identifier for target in self.config_list_targets if target.identifier not in hidden_ids
		}
		self.mount_config_list_visibility()

	def mount_config_list_visibility(self) -> None:
		name_counts: dict[str, int] = {}
		for target in self.config_list_targets:
			name_counts[target.name] = name_counts.get(target.name, 0) + 1
		options = [
			(self.format_config_list_option(target, name_counts[target.name] > 1), ("config_list", target.identifier))
			for target in sort_reminders_targets(
				self.config_list_targets,
				self.config.reminders_list_sort_order,
				self.config.reminders_list_usage_counts,
			)
		]
		menu = self.build_list(options, list_type=ConfigListVisibilityView)
		self.replace_body(menu)
		menu.focus()

	def format_config_list_option(self, target: DeliveryTargetOption, show_detail: bool) -> str:
		state = "[x]" if target.identifier in self.config_visible_list_ids else "[ ]"
		return f"{state} {format_target_label(target, show_detail)}"

	def toggle_current_config_list(self, cursor_index: int | None) -> None:
		if self.view_name != "config_lists" or cursor_index is None:
			return
		list_view = self.query_one(ListView)
		item = list_view.children[cursor_index]
		if not isinstance(item, OptionItem):
			return
		value = item.value
		if not (isinstance(value, tuple) and value[0] == "config_list" and isinstance(value[1], str)):
			return
		target_id = value[1]
		if target_id in self.config_visible_list_ids:
			self.config_visible_list_ids.discard(target_id)
		else:
			self.config_visible_list_ids.add(target_id)
		target = next((target for target in self.config_list_targets if target.identifier == target_id), None)
		if target is None:
			return
		name_counts: dict[str, int] = {}
		for list_target in self.config_list_targets:
			name_counts[list_target.name] = name_counts.get(list_target.name, 0) + 1
		item.set_label(self.format_config_list_option(target, name_counts[target.name] > 1))

	def save_config_list_visibility(self) -> None:
		if self.view_name != "config_lists":
			return
		self.config = replace(
			self.config,
			hidden_apple_reminders_list_ids=[
				target.identifier
				for target in self.config_list_targets
				if target.identifier not in self.config_visible_list_ids
			],
		)
		self.save_current_config()
		self.show_config_menu()

	def show_config_defaults_menu(self) -> None:
		self.view_name = "config_defaults"
		self.set_header("Defaults", "Choose the starting settings used when adding items from a template.")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				(f"Default Reminder List: {self.config.apple_reminders_list_name}", "config:default_list"),
				(f"Include All On-Hand Items: {format_bool(self.config.include_on_hand_default)}", "config:include_on_hand"),
				(f"Append Short Name: {format_bool(self.config.append_short_name)}", "config:append_short_name"),
			]
		)
		self.replace_body(menu)
		menu.focus()

	def show_config_default_list(self) -> None:
		self.view_name = "config_default_list"
		self.set_header(
			"Default Destination",
			"Choose which Reminders list to preselect when adding items. This should be the list you add things to most often.",
		)
		self.set_footer("[↑↓ select | ENTER save | ESC back | Ctrl-C quit]")
		try:
			targets = AppleRemindersTarget().list_targets()
		except DeliveryError as error:
			self.show_error(str(error))
			return
		visible_targets = [
			target for target in targets if target.identifier not in self.config.hidden_apple_reminders_list_ids
		]
		if len(visible_targets) == 0:
			self.show_error("No visible Reminders lists are available.")
			return
		name_counts: dict[str, int] = {}
		for target in visible_targets:
			name_counts[target.name] = name_counts.get(target.name, 0) + 1
		options = [
			(format_target_label(target, name_counts[target.name] > 1), target)
			for target in sort_reminders_targets(
				visible_targets,
				self.config.reminders_list_sort_order,
				self.config.reminders_list_usage_counts,
			)
		]
		menu = self.build_list(options, default_value=self.config.apple_reminders_list_id or self.config.apple_reminders_list_name)
		self.replace_body(menu)
		menu.focus()

	def save_default_reminders_list(self, target: DeliveryTargetOption) -> None:
		self.config = replace(
			self.config,
			apple_reminders_list_id=target.identifier,
			apple_reminders_list_name=target.name,
		)
		self.save_current_config()
		self.show_config_defaults_menu()

	def show_config_bool_option(self, setting_name: str) -> None:
		self.view_name = f"config_bool:{setting_name}"
		if setting_name == "include_on_hand_default":
			self.set_header(
				"Start with On-Hand Items Selected?",
				"For templates with on-hand items, choose whether those items start checked during review.",
			)
		elif setting_name == "append_short_name":
			self.set_header(
				"Append Short Name?",
				"Choose whether to add the template short name to generated reminder titles. This is most helpful for recipes, so you can tell which items belong to a recipe when similar items already exist on your regular shopping list.",
			)
		else:
			self.set_header(format_config_setting_name(setting_name), "Choose the default value for this setting.")
		self.set_footer("[↑↓ select | ENTER save | ESC back | Ctrl-C quit]")
		current_value = bool(getattr(self.config, setting_name))
		options = [("Yes", True), ("No", False)] if current_value else [("No", False), ("Yes", True)]
		menu = self.build_list(options)
		self.replace_body(menu)
		menu.focus()

	def save_config_bool_option(self, value: bool) -> None:
		if self.view_name == "config_bool:include_on_hand_default":
			self.config = replace(self.config, include_on_hand_default=value)
		elif self.view_name == "config_bool:append_short_name":
			self.config = replace(self.config, append_short_name=value)
		self.save_current_config()
		self.show_config_defaults_menu()

	def show_config_colors_menu(self) -> None:
		self.view_name = "config_colors"
		self.set_header("Colors", "Choose the colors used across screens and generated output.")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		menu = self.build_list(
			[
				(format_color_setting_label(self.config, "standard_text_color"), "config:color:standard_text_color"),
				(format_color_setting_label(self.config, "quantity_color"), "config:color:quantity_color"),
				(format_color_setting_label(self.config, "selection_color"), "config:color:selection_color"),
				(format_color_setting_label(self.config, "omitted_ingredient_color"), "config:color:omitted_ingredient_color"),
			],
			markup=True,
		)
		self.replace_body(menu)
		menu.focus()

	def show_config_color_picker(self, setting_name: str) -> None:
		self.view_name = "config_color_picker"
		self.config_color_setting = setting_name
		self.set_header(COLOR_SETTING_LABELS[setting_name], "Choose a named color. Edit config.json directly for custom hex colors.")
		self.set_footer("[↑↓ select | ENTER save | ESC back | Ctrl-C quit]")
		current_color = normalize_config_color(setting_name, getattr(self.config, setting_name))
		choice_values = [CONFIG_COLOR_DEFAULTS[setting_name], *CONFIG_COLOR_OPTIONS]
		if current_color not in choice_values:
			choice_values.insert(0, current_color)
		seen_colors: set[str] = set()
		options: list[tuple[str, object]] = []
		for color in choice_values:
			if color in seen_colors:
				continue
			seen_colors.add(color)
			label = format_color_choice_label(color, color == CONFIG_COLOR_DEFAULTS[setting_name])
			options.append((label, f"config:set_color:{color}"))
		menu = self.build_list(options, default_value=f"config:set_color:{current_color}", markup=True)
		self.replace_body(menu)
		menu.focus()

	def save_config_color(self, color: str) -> None:
		if self.config_color_setting == "":
			return
		normalized_color = normalize_config_color(self.config_color_setting, color)
		self.config = replace(self.config, **{self.config_color_setting: normalized_color})
		self.save_current_config()
		self.show_config_colors_menu()

	def show_update_screen(self) -> None:
		self.view_name = "config_updates"
		self.update_status = self.get_update_status()
		self.update_check_requested = True
		status = self.update_status
		if status.error != "":
			self.show_config_menu()
			return
		if status.latest_release is None and status.skipped_release is None:
			self.show_config_menu()
			return
		release = status.latest_release or status.skipped_release
		assert release is not None
		self.update_release = release
		self.set_header("Update Available", f"Current: {status.current_version}  Latest: {release.version}")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		body = render_update_summary(release)
		menu = self.build_list(
			[
				(f"Update to v{release.version}", "config:run_update"),
				("View Release on GitHub", "config:view_release"),
				(f"Skip v{release.version}", f"config:skip_update:{release.version}"),
				("↩ Back", "config:updates_back"),
			]
		)
		self.replace_body(Static(body), menu)
		menu.focus()

	def get_update_status(self) -> UpdateStatus:
		current_version = get_current_version()
		try:
			latest_release = fetch_latest_release()
		except UpdateCheckError as error:
			return UpdateStatus(current_version=current_version, error=str(error))
		if not is_newer_version(latest_release.version, current_version):
			return UpdateStatus(current_version=current_version)
		if latest_release.version == self.config.skipped_update_version:
			return UpdateStatus(current_version=current_version, skipped_release=latest_release)
		return UpdateStatus(current_version=current_version, latest_release=latest_release)

	def run_update(self) -> None:
		release = self.update_release
		if release is None:
			self.show_update_screen()
			return

		self.view_name = "config_update_running"
		self.set_header("Updating ListKit", f"Installing v{release.version}. This may take a moment.")
		self.set_footer("[Ctrl-C quit]")
		self.replace_body(
			Static("Running update..."),
			ProgressBar(total=None, show_percentage=False, show_eta=False, id="update-progress"),
		)
		self.update_worker = self.run_worker(
			lambda: run_package_update(release.version),
			name="package-update",
			thread=True,
			exclusive=True,
		)

	def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
		if event.worker is not self.update_worker:
			return
		release = self.update_release
		if event.state == WorkerState.ERROR:
			result = UpdateResult(success=False, command=(), output="", error="Update worker failed unexpectedly.")
			self.update_result = result
			if release is not None:
				self.show_update_failure(release, result)
			return
		if event.state != WorkerState.SUCCESS:
			return
		result = event.worker.result
		if release is None or not isinstance(result, UpdateResult):
			self.show_update_screen()
			return
		self.update_result = result
		if result.success:
			self.show_update_success(release)
		else:
			self.show_update_failure(release, result)

	def show_update_success(self, release: ReleaseInfo) -> None:
		self.view_name = "config_update_success"
		self.set_header("Update Complete", f"Successfully updated to v{release.version}. Restart required.")
		self.set_footer("[ENTER quit and relaunch | Ctrl-C quit]")
		body = "ListKit needs to restart before the new version is active."
		menu = self.build_list([("Quit and Relaunch", "config:relaunch")])
		self.replace_body(Static(body), menu)
		menu.focus()

	def show_update_failure(self, release: ReleaseInfo, result: UpdateResult) -> None:
		self.view_name = "config_update_failure"
		self.set_header("Update Failed", f"v{release.version} could not be installed.")
		self.set_footer("[↑↓ select | ENTER confirm | ESC back | Ctrl-C quit]")
		body = render_update_failure(result)
		menu = self.build_list(
			[
				("Copy Error and Open GitHub Issue", "config:copy_error_issue"),
				("Copy Error", "config:copy_error"),
				("View Release on GitHub", "config:view_release"),
				("↩ Back", "config:updates_back"),
			]
		)
		self.replace_body(Static(body), menu)
		menu.focus()

	def view_release_on_github(self) -> None:
		if self.update_release is None or self.update_release.url == "":
			self.query_one("#context", Static).update("Release URL is unavailable.")
			return
		webbrowser.open(self.update_release.url)
		self.query_one("#context", Static).update("Opened release in your default browser.")

	def copy_update_error(self, open_issue: bool = False) -> None:
		if self.update_result is None:
			self.query_one("#context", Static).update("No update error is available.")
			return
		copied = copy_text_to_clipboard(render_update_failure(self.update_result))
		if open_issue:
			webbrowser.open(GITHUB_ISSUES_URL)
			message = "Copied update error and opened GitHub Issues." if copied else "Opened GitHub Issues. Could not copy update error."
		else:
			message = "Copied update error." if copied else "Could not copy update error."
		self.query_one("#context", Static).update(message)

	def relaunch(self) -> None:
		self.exit(RELAUNCH_RESULT_CODE)

	def skip_update(self, version: str) -> None:
		self.config = replace(self.config, skipped_update_version=version)
		self.save_current_config()
		self.update_status = self.get_update_status()
		self.show_config_menu()

	def handle_config_action(self, value: str) -> None:
		if value == "config:lists":
			self.show_config_list_visibility()
		elif value == "config:sort_order":
			self.show_config_sort_order_menu()
		elif value == "config:sort_order_back":
			self.show_config_menu()
		elif value == "config:sort_picker_back":
			self.show_config_sort_order_menu()
		elif value == "config:usage_history":
			self.show_usage_history_menu()
		elif value == "config:usage_history_back":
			self.show_config_menu()
		elif value == "config:template_usage":
			self.show_template_usage_history()
		elif value == "config:list_usage":
			self.show_list_usage_history()
		elif value == "config:usage_picker_back":
			self.show_usage_history_menu()
		elif value == "config:confirm_reset_template_usage":
			self.show_reset_usage_confirmation("template")
		elif value == "config:confirm_reset_list_usage":
			self.show_reset_usage_confirmation("list")
		elif value.startswith("config:reset_usage_back:"):
			self.return_from_reset_usage_confirmation(value.rsplit(":", 1)[1])
		elif value.startswith("config:reset_usage:"):
			self.reset_usage_history(value.rsplit(":", 1)[1])
		elif value == "config:open_config":
			self.open_config_file()
		elif value == "config:colors":
			self.show_config_colors_menu()
		elif value == "config:defaults":
			self.show_config_defaults_menu()
		elif value == "config:updates":
			self.show_update_screen()
		elif value == "config:updates_current":
			return
		elif value == "config:return":
			self.short_name = None
			self.show_main_menu()
		elif value == "config:exit":
			self.exit(0)
		elif value == "config:default_list":
			self.show_config_default_list()
		elif value == "config:include_on_hand":
			self.show_config_bool_option("include_on_hand_default")
		elif value == "config:append_short_name":
			self.show_config_bool_option("append_short_name")
		elif value in {"config:template_sort_order", "config:reminders_list_sort_order"}:
			self.show_config_sort_order_picker(value.removeprefix("config:"))
		elif value.startswith("config:set_sort:"):
			_parts = value.split(":")
			self.save_config_sort_order(_parts[2], _parts[3])
		elif value.startswith("config:color:"):
			self.show_config_color_picker(value.rsplit(":", 1)[1])
		elif value.startswith("config:set_color:"):
			self.save_config_color(value.rsplit(":", 1)[1])
		elif value == "config:run_update":
			self.run_update()
		elif value == "config:view_release":
			self.view_release_on_github()
		elif value == "config:copy_error":
			self.copy_update_error()
		elif value == "config:copy_error_issue":
			self.copy_update_error(open_issue=True)
		elif value == "config:relaunch":
			self.relaunch()
		elif value.startswith("config:skip_update:"):
			self.skip_update(value.rsplit(":", 1)[1])
		elif value == "config:updates_back":
			self.show_config_menu()

	def save_current_config(self) -> None:
		if self.config_path is not None:
			save_config(self.config_path, self.config)

	def record_template_usage(self) -> None:
		if self.template_id == "":
			return
		usage_counts = dict(self.config.template_usage_counts)
		template_name = self.template["name"] if self.template is not None else self.template_id
		usage_counts[self.template_id] = {
			"name": str(template_name),
			"count": usage_record_count(usage_counts.get(self.template_id)) + 1,
		}
		self.config = replace(self.config, template_usage_counts=usage_counts)

	def record_reminders_list_usage(self, target: DeliveryTargetOption) -> None:
		if target.identifier == "":
			return
		usage_counts = dict(self.config.reminders_list_usage_counts)
		usage_counts[target.identifier] = {
			"name": target.name,
			"count": usage_record_count(usage_counts.get(target.identifier)) + 1,
		}
		self.config = replace(self.config, reminders_list_usage_counts=usage_counts)

	def open_templates_folder(self) -> None:
		self.ensure_template_folders()
		try:
			subprocess.run(["open", str(self.templates_path)], check=True)
		except (OSError, subprocess.CalledProcessError):
			webbrowser.open(self.templates_path.as_uri())
		self.query_one("#context", Static).update("Opened templates folder.")

	def open_documentation(self) -> None:
		docs_path = Path(__file__).resolve().parents[1] / "TEMPLATES.md"
		if not docs_path.exists():
			self.query_one("#context", Static).update("Documentation file not found.")
			return
		webbrowser.open(docs_path.as_uri())
		self.query_one("#context", Static).update("Opened TEMPLATES.md.")

	def open_config_file(self) -> None:
		if self.config_path is None:
			self.query_one("#context", Static).update("Config file path is unavailable.")
			return
		if not self.config_path.exists():
			save_config(self.config_path, self.config)
		try:
			subprocess.run(["open", str(self.config_path)], check=True)
		except (OSError, subprocess.CalledProcessError):
			webbrowser.open(self.config_path.as_uri())
		self.query_one("#context", Static).update("Opened config.json.")

	def ensure_template_folders(self) -> None:
		self.templates_path.mkdir(parents=True, exist_ok=True)
		(self.templates_path / "lists").mkdir(exist_ok=True)
		(self.templates_path / "recipes").mkdir(exist_ok=True)

	def set_header(self, title: str, context: str, markup: bool = False) -> None:
		self.query_one("#title", Static).update(title if markup else escape(title))
		self.query_one("#context", Static).update(escape(context))

	def set_footer(self, text: str) -> None:
		self.query_one("#footer-note", Static).update(text)

	def mount_list(
		self,
		options: list[tuple[str, object]],
		default_value: object | None = None,
		default_index: int | None = None,
		list_type: type[ListView] = WrappingListView,
	) -> None:
		list_view = self.build_list(options, default_value=default_value, default_index=default_index, list_type=list_type)
		self.replace_body(list_view)
		list_view.focus()

	def build_list(
		self,
		options: list[tuple[str, object] | tuple[str, object, bool]],
		default_value: object | None = None,
		default_index: int | None = None,
		list_type: type[ListView] = WrappingListView,
		markup: bool = False,
	) -> ListView:
		items: list[OptionItem] = [
			OptionItem(option[0], option[1], selectable=option[2] if len(option) > 2 else True, markup=markup)
			for option in options
		]
		list_view = list_type(*items)
		if default_index is not None and 0 <= default_index < len(items):
			list_view.index = default_index
			self.call_after_refresh(self.restore_list_index, list_view, default_index)
		elif default_value is not None:
			for index, item in enumerate(items):
				value = item.value
				if isinstance(value, DeliveryTargetOption) and default_value in {value.identifier, value.name}:
					list_view.index = index
					self.call_after_refresh(self.restore_list_index, list_view, index)
					break
				if value == default_value:
					list_view.index = index
					self.call_after_refresh(self.restore_list_index, list_view, index)
					break
		if list_view.index is None or not items[list_view.index].selectable:
			for index, item in enumerate(items):
				if item.selectable and item.label_text.strip():
					list_view.index = index
					break
		return list_view

	def restore_list_index(self, list_view: ListView, index: int) -> None:
		if list_view.is_attached and 0 <= index < len(list_view.children):
			list_view.index = index

	def replace_body(self, *children: object) -> None:
		body = self.query_one("#body", Vertical)
		body.remove_children()
		for child in children:
			body.mount(child)  # type: ignore[arg-type]

	def on_list_view_selected(self, event: ListView.Selected) -> None:
		item = event.item
		if not isinstance(item, OptionItem):
			return
		if not item.selectable:
			return
		value = item.value
		if isinstance(value, tuple) and value[0] == "toggle_item" and isinstance(value[1], int):
			self.items_cursor_index = event.list_view.index or 0
			self.toggle_ingredient_item(item, value[1])
			return
		self.handle_action(value)

	def handle_action(self, value: object) -> None:
		if value == "exit":
			self.exit(self.result_code)
		elif value == "back":
			self.action_back()
		elif value == "create_list":
			self.show_template_menu()
		elif value == "create_template":
			self.show_create_template_source_screen()
		elif value == "config":
			self.show_config_menu()
		elif value == "help":
			self.show_help()
		elif value == "help:open_templates":
			self.open_templates_folder()
		elif value == "help:open_docs":
			self.open_documentation()
		elif value == "create_target":
			self.show_new_list_screen()
		elif isinstance(value, DeliveryTargetOption):
			if self.view_name == "config_default_list":
				self.save_default_reminders_list(value)
			else:
				self.delivery_target = value
				self.create_reminders()
		elif isinstance(value, tuple) and value[0] == "template_source" and isinstance(value[1], DeliveryTargetOption):
			self.submit_template_source(value[1])
		elif isinstance(value, tuple) and value[0] == "template" and isinstance(value[1], str):
			template = self.templates.get(value[1])
			if template is not None:
				self.start_template(template, value[1])
		elif isinstance(value, dict):
			self.start_template(value)
		elif isinstance(value, bool):
			if self.view_name.startswith("config_bool:"):
				self.save_config_bool_option(value)
			else:
				self.include_on_hand = value
				self.build_items()
		elif isinstance(value, str) and value.startswith("config:"):
			self.handle_config_action(value)

	def toggle_current_ingredient(self, cursor_index: int | None) -> None:
		if self.view_name != "items":
			return
		list_view = self.query_one(ListView)
		if cursor_index is None:
			return
		self.items_cursor_index = cursor_index
		item = list_view.children[cursor_index]
		if not isinstance(item, OptionItem):
			return
		value = item.value
		if not (isinstance(value, tuple) and value[0] == "toggle_item" and isinstance(value[1], int)):
			return
		self.toggle_ingredient_item(item, value[1])

	def toggle_ingredient_item(self, item: OptionItem, item_index: int) -> None:
		assert self.shopping_list is not None
		self.items_cursor_value = ("toggle_item", item_index)
		if item_index in self.selected_item_indexes:
			self.selected_item_indexes.discard(item_index)
		else:
			self.selected_item_indexes.add(item_index)

		ordered_items = order_items_with_on_hand_last(self.shopping_list.items)
		prefix_width = max((len(format_item_prefix(ordered_item)) for _index, ordered_item in ordered_items), default=0)
		item.set_label(self.format_ingredient_option(item_index, self.shopping_list.items[item_index], prefix_width))

	def format_ingredient_option(self, index: int, item: ShoppingListItem, prefix_width: int) -> str:
		state = "[x]" if index in self.selected_item_indexes else "[ ]"
		return f"{state} {format_item(replace(item, tag=None), prefix_width)}"

	def continue_from_ingredients(self, cursor_index: int | None) -> None:
		if self.view_name != "items":
			return
		list_view = self.query_one(ListView)
		if cursor_index is not None:
			item = list_view.children[cursor_index]
			if isinstance(item, OptionItem) and item.value == "back":
				self.action_back()
				return
		self.shopping_list = apply_selected_ingredients(self.shopping_list, sorted(self.selected_item_indexes))
		self.show_target_screen()

	def on_input_submitted(self, event: Input.Submitted) -> None:
		if event.input.id == "batch-input":
			self.submit_batch(event.value)
		elif event.input.id == "new-list-input":
			self.create_target(event.value)
		elif event.input.id == "template-name-input":
			self.submit_template_name(event.value)
		elif event.input.id == "template-short-name-input":
			self.submit_template_short_name(event.value)

	def submit_batch(self, value: str) -> None:
		try:
			self.batch_size = float(value.strip())
		except ValueError:
			self.show_batch_screen()
			self.query_one("#context", Static).update("Batch size must be a number.")
			return
		if self.batch_size <= 0:
			self.show_batch_screen()
			self.query_one("#context", Static).update("Batch size must be greater than zero.")
			return
		self.show_on_hand_screen()

	def action_continue(self) -> None:
		if self.view_name == "result":
			self.show_template_menu()
		elif self.view_name == "help":
			self.show_main_menu()
		elif self.view_name == "error":
			self.exit(self.result_code)
		elif self.view_name == "config_update_success":
			self.relaunch()
		elif self.view_name == "config_updates":
			self.show_config_menu()

	def action_back(self) -> None:
		if self.view_name == "main":
			self.exit(0)
		elif self.view_name == "config":
			if self.start_config:
				self.exit(0)
			else:
				self.show_main_menu()
		elif self.view_name in {
			"config_lists",
			"config_sort_order",
			"config_usage_history",
			"config_colors",
			"config_defaults",
			"config_updates",
			"config_update_failure",
		}:
			self.show_config_menu()
		elif self.view_name.startswith("config_sort:"):
			self.show_config_sort_order_menu()
		elif self.view_name in {"config_template_usage", "config_list_usage"}:
			self.show_usage_history_menu()
		elif self.view_name == "config_confirm_reset:template":
			self.show_template_usage_history()
		elif self.view_name == "config_confirm_reset:list":
			self.show_list_usage_history()
		elif self.view_name == "config_default_list":
			self.show_config_defaults_menu()
		elif self.view_name.startswith("config_bool:"):
			self.show_config_defaults_menu()
		elif self.view_name == "config_color_picker":
			self.show_config_colors_menu()
		elif self.view_name == "template":
			self.show_main_menu()
		elif self.view_name == "template_source":
			self.show_main_menu()
		elif self.view_name == "template_name":
			self.show_create_template_source_screen()
		elif self.view_name == "template_short_name":
			self.show_template_name_screen()
		elif self.view_name == "batch":
			self.show_template_menu() if self.short_name is None else self.exit(130)
		elif self.view_name == "on_hand":
			if self.template is not None and template_uses_batch_size(self.template):
				self.show_batch_screen()
			else:
				self.show_template_menu() if self.short_name is None else self.exit(130)
		elif self.view_name == "items":
			if self.template is not None and template_has_on_hand_items(self.template):
				self.show_on_hand_screen()
			elif self.template is not None and template_uses_batch_size(self.template):
				self.show_batch_screen()
			else:
				self.show_template_menu() if self.short_name is None else self.exit(130)
		elif self.view_name == "new_list":
			self.show_target_screen()
		elif self.view_name == "target" and self.shopping_list is not None:
			self.show_items_screen()
		elif self.view_name in {"help", "result"}:
			self.show_main_menu()
		else:
			self.exit(self.result_code)

	def action_quit_app(self) -> None:
		self.result_code = 130
		self.exit(self.result_code)


def run_textual_listkit(
	config: Config,
	templates_path: Path,
	short_name: str | None = None,
	config_path: Path | None = None,
	start_config: bool = False,
) -> int:
	app = ListKitApp(
		config=config,
		templates_path=templates_path,
		short_name=short_name,
		config_path=config_path,
		start_config=start_config,
	)
	result = app.run()
	if result in {10, 20, RELAUNCH_RESULT_CODE}:
		return int(result)
	return app.result_code


def format_target_label(target: DeliveryTargetOption, show_detail: bool) -> str:
	label = f"{target.name} ({target.item_count})"
	if not show_detail:
		return label
	if len(target.sample_items) == 0:
		return f"{label} - list is empty"
	samples = ", ".join(truncate_sample_item(item) for item in target.sample_items[:3])
	return f"{label} - {samples}"


def truncate_sample_item(item: str) -> str:
	return item if len(item) <= 11 else f"{item[:11]}..."


def sort_templates(
	templates: TemplateMap,
	sort_order: str,
	usage_counts: dict[str, object] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
	items = list(templates.items())
	usage_counts = usage_counts or {}
	if sort_order == "name_desc":
		return sorted(items, key=lambda entry: entry[1]["name"].casefold(), reverse=True)
	if sort_order == "most_frequently_used":
		return sorted(items, key=lambda entry: (-usage_record_count(usage_counts.get(entry[0])), entry[1]["name"].casefold()))
	return sorted(items, key=lambda entry: entry[1]["name"].casefold())


def sort_reminders_targets(
	targets: list[DeliveryTargetOption],
	sort_order: str,
	usage_counts: dict[str, object] | None = None,
) -> list[DeliveryTargetOption]:
	usage_counts = usage_counts or {}
	if sort_order == "name_desc":
		return sorted(targets, key=lambda target: target.name.casefold(), reverse=True)
	if sort_order == "most_frequently_used":
		return sorted(targets, key=lambda target: (-usage_record_count(usage_counts.get(target.identifier)), target.name.casefold()))
	if sort_order == "item_count_asc":
		return sorted(targets, key=lambda target: (target.item_count, target.name.casefold()))
	if sort_order == "item_count_desc":
		return sorted(targets, key=lambda target: (-target.item_count, target.name.casefold()))
	return sorted(targets, key=lambda target: target.name.casefold())


def template_item_count(template: dict[str, Any]) -> int:
	items = template.get("ingredients", template.get("items", []))
	if not isinstance(items, list):
		return 0
	return sum(
		1
		for item in items
		if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip() != ""
	)


def format_sort_order_label(sort_order: str) -> str:
	return SORT_ORDER_LABELS.get(sort_order, SORT_ORDER_LABELS["name_asc"])


def format_template_usage_rows(templates: TemplateMap, usage_counts: dict[str, object]) -> list[str]:
	rows: list[tuple[str, int]] = [
		(template["name"], usage_record_count(usage_counts.get(template_id)))
		for template_id, template in templates.items()
	]
	rows.extend(
		(format_missing_usage_label("Missing template", template_id, record), usage_record_count(record))
		for template_id, record in usage_counts.items()
		if template_id not in templates and usage_record_count(record) > 0
	)
	return format_usage_rows(rows)


def format_reminders_list_usage_rows(
	targets: list[DeliveryTargetOption],
	usage_counts: dict[str, object],
) -> list[str]:
	target_names = {target.identifier: target.name for target in targets}
	rows: list[tuple[str, int]] = [
		(target.name, usage_record_count(usage_counts.get(target.identifier)))
		for target in targets
	]
	rows.extend(
		(format_missing_usage_label("Missing list", target_id, record), usage_record_count(record))
		for target_id, record in usage_counts.items()
		if target_id not in target_names and usage_record_count(record) > 0
	)
	return format_usage_rows(rows)


def format_usage_rows(rows: list[tuple[str, int]]) -> list[str]:
	return [
		"-" * 36,
		*[
			f"{label}: {count}"
			for label, count in sorted(rows, key=lambda row: (-row[1], row[0].casefold()))
		],
	]


def usage_record_count(record: object) -> int:
	if isinstance(record, int):
		return record if record >= 0 else 0
	if isinstance(record, dict):
		count = record.get("count")
		return count if isinstance(count, int) and count >= 0 else 0
	return 0


def usage_record_name(record: object) -> str:
	if not isinstance(record, dict):
		return ""
	name = record.get("name", "")
	return name if isinstance(name, str) else ""


def format_missing_usage_label(prefix: str, identifier: str, record: object) -> str:
	name = usage_record_name(record)
	if name == "":
		return f"{prefix}: {identifier}"
	return f"{prefix}: {name} ({identifier})"


def order_items_with_on_hand_last(items: list[ShoppingListItem]) -> list[tuple[int, ShoppingListItem]]:
	return sorted(enumerate(items), key=lambda pair: pair[1].always_on_hand)


def apply_selected_ingredients(shopping_list: ShoppingList, selected_indexes: list[int]) -> ShoppingList:
	selected_index_set = set(selected_indexes)
	items = [
		replace(item, omitted=index not in selected_index_set)
		for index, item in enumerate(shopping_list.items)
	]
	return ShoppingList(
		recipe_name=shopping_list.recipe_name,
		batch_size=shopping_list.batch_size,
		items=items,
		included_items=[item for item in items if not item.omitted],
		omitted_items=[item for item in items if item.omitted],
	)


def render_created_items_summary(created_items: list[str]) -> str:
	lines: list[str] = ["-" * 36]
	for item in created_items:
		lines.append(f"- {item}")
	return "\n".join(lines)


def format_settings_context(status: UpdateStatus) -> str:
	if status.latest_release is not None:
		return f"Choose what you want to configure. v{status.latest_release.version} is available."
	if status.skipped_release is not None:
		return f"Choose what you want to configure. v{status.skipped_release.version} is available but skipped."
	if status.error != "":
		return f"Choose what you want to configure. Current version: v{status.current_version}."
	return f"Choose what you want to configure. v{status.current_version} is up to date."


def format_update_menu_label(status: UpdateStatus, check_requested: bool = False) -> str:
	if status.latest_release is not None:
		return f"Update to v{status.latest_release.version}"
	if status.skipped_release is not None:
		return f"Update to v{status.skipped_release.version}"
	if status.error != "" and check_requested:
		return "Check for Updates: unavailable"
	if check_requested:
		return "Check for Updates: up to date"
	return "Check for Updates"


def is_empty_templates_error(error: TemplateLoadError) -> bool:
	message = str(error)
	return message.startswith("Template path not found:") or message.startswith("No template JSON files found in:")


def format_bool(value: bool) -> str:
	return "Yes" if value else "No"


def format_config_setting_name(setting_name: str) -> str:
	return setting_name.replace("_", " ").title()


def normalize_config_color(setting_name: str, color_name: str) -> str:
	if color_name == "default":
		return CONFIG_COLOR_DEFAULTS[setting_name]
	return normalize_color(color_name, CONFIG_COLOR_DEFAULTS[setting_name])


def format_color_setting_label(config: Config, setting_name: str) -> str:
	color = normalize_config_color(setting_name, getattr(config, setting_name))
	return f"{escape(COLOR_SETTING_LABELS[setting_name])}: {format_color_markup(color)}"


def format_color_choice_label(color: str, is_default: bool) -> str:
	label = format_color_markup(color)
	if is_default:
		return f"{label} (default)"
	return label


def format_color_markup(color: str) -> str:
	style = TEXTUAL_COLOR_STYLES.get(color, color if HEX_COLOR_PATTERN.match(color) else "")
	if style == "":
		return escape(color)
	return f"[{style}]{escape(color)}[/]"


def template_with_valid_items(template: dict[str, Any]) -> dict[str, Any] | None:
	items = [
		dict(item)
		for item in template.get("ingredients", template.get("items", []))
		if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip() != ""
	]
	if len(items) == 0:
		return None
	valid_template = dict(template)
	valid_template["ingredients"] = items
	valid_template["items"] = items
	return valid_template


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
			for item_name in item_names or [""]
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


def render_update_summary(release: ReleaseInfo) -> str:
	lines = [
		f"Release: {release.name or release.version}",
		f"URL: {release.url}",
		"",
		"Changelog",
		"-" * 36,
		release.body.strip() or "No release notes provided.",
		"",
	]
	return "\n".join(lines)


def render_update_failure(result: UpdateResult) -> str:
	lines = ["Update failed."]
	if result.command:
		lines.extend(["", "Command", "-" * 36, " ".join(result.command)])
	if result.error != "":
		lines.extend(["", "Error", "-" * 36, result.error])
	if result.output != "":
		lines.extend(["", "Output", "-" * 36, result.output])
	return "\n".join(lines)


def copy_text_to_clipboard(text: str) -> bool:
	try:
		subprocess.run(["pbcopy"], input=text, text=True, check=True)
	except (OSError, subprocess.CalledProcessError):
		return False
	return True
