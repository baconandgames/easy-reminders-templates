from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from recipe_shopper.config import Config
from recipe_shopper.formatter import ShoppingList, format_delivery_item

TargetSelector = Callable[[str, list["DeliveryTargetOption"], int], "DeliveryTargetOption"]
CREATE_NEW_LIST_IDENTIFIER: str = "__create_new_list__"


@dataclass(frozen=True)
class DeliveryResult:
	target_app: str
	target_name: str
	created_items: list[str]
	omitted_items: list[str]


@dataclass(frozen=True)
class DeliveryTargetOption:
	identifier: str
	name: str
	source: str
	item_count: int
	sample_items: list[str]


class DeliveryError(Exception):
	"""Raised when delivery to a target app fails."""


class DeliveryTarget(Protocol):
	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		pass


class AppleRemindersTarget:
	target_app: str = "apple_reminders"
	target_name: str = "Apple Reminders"

	def __init__(
		self,
		runner=subprocess.run,
		target_selector: TargetSelector | None = None,
	) -> None:
		self._runner = runner
		self._target_selector = target_selector

	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		created_items: list[str] = [format_delivery_item(item) for item in shopping_list.included_items]
		omitted_items: list[str] = [format_delivery_item(item) for item in shopping_list.omitted_items]
		selected_target: DeliveryTargetOption = self._resolve_list_target(config)
		self._run_helper(
			created_items,
			selected_target.identifier,
			selected_target.name,
		)

		return DeliveryResult(
			target_app=self.target_app,
			target_name=f"{self.target_name}: {selected_target.name}",
			created_items=created_items,
			omitted_items=omitted_items,
		)

	def list_targets(self) -> list[DeliveryTargetOption]:
		helper_path: Path = get_reminders_helper_path()
		try:
			result = self._runner(
				["swift", str(helper_path), "list-targets"],
				input="",
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or "Could not list Apple Reminders targets."
			raise DeliveryError(message) from error

		try:
			targets: list[dict[str, object]] = json.loads(result.stdout)
		except json.JSONDecodeError as error:
			raise DeliveryError("Could not parse Apple Reminders targets.") from error

		return [
			DeliveryTargetOption(
				identifier=str(target["id"]),
				name=str(target["name"]),
				source=str(target["source"]),
				item_count=int(target["item_count"]),
				sample_items=[str(item) for item in target.get("sample_items", [])],
			)
			for target in targets
		]

	def create_target(self, list_name: str) -> DeliveryTargetOption:
		helper_path: Path = get_reminders_helper_path()
		try:
			result = self._runner(
				["swift", str(helper_path), "create-list"],
				input=list_name,
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or f'Could not create Apple Reminders list "{list_name}".'
			raise DeliveryError(message) from error

		try:
			target: dict[str, object] = json.loads(result.stdout)
		except json.JSONDecodeError as error:
			raise DeliveryError("Could not parse created Apple Reminders list.") from error

		return DeliveryTargetOption(
			identifier=str(target["id"]),
			name=str(target["name"]),
			source=str(target["source"]),
			item_count=int(target["item_count"]),
			sample_items=[str(item) for item in target.get("sample_items", [])],
		)

	def _resolve_list_target(self, config: Config) -> DeliveryTargetOption:
		targets: list[DeliveryTargetOption] = self.list_targets()
		visible_targets: list[DeliveryTargetOption] = [
			target for target in targets if target.identifier not in config.hidden_apple_reminders_list_ids
		]
		omitted_count: int = len(targets) - len(visible_targets)

		if self._target_selector is not None:
			return self._target_selector(config.apple_reminders_list_name, visible_targets, omitted_count)

		if len(visible_targets) == 0:
			raise DeliveryError("No Apple Reminders lists were found.")

		if config.apple_reminders_list_id:
			for target in visible_targets:
				if target.identifier == config.apple_reminders_list_id:
					return target

			raise DeliveryError(f"Reminder list not found: {config.apple_reminders_list_id}")

		matches: list[DeliveryTargetOption] = [
			target for target in visible_targets if target.name == config.apple_reminders_list_name
		]

		if len(matches) == 0:
			raise DeliveryError(f"Reminder list not found: {config.apple_reminders_list_name}")

		if len(matches) == 1:
			return matches[0]

		raise DeliveryError(f'Multiple reminder lists named "{config.apple_reminders_list_name}" were found.')

	def _run_helper(
		self,
		created_items: list[str],
		list_identifier: str | None,
		list_name: str,
	) -> None:
		helper_path: Path = get_reminders_helper_path()
		payload: str = json.dumps(
			{
				"listIdentifier": list_identifier,
				"listName": list_name,
				"items": created_items,
			}
		)
		try:
			self._runner(
				["swift", str(helper_path), "create-reminders"],
				input=payload,
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or "Apple Reminders delivery failed."
			raise DeliveryError(message) from error


def get_delivery_target(
	target_app: str,
	target_selector: TargetSelector | None = None,
) -> DeliveryTarget:
	if target_app == AppleRemindersTarget.target_app:
		return AppleRemindersTarget(target_selector=target_selector)

	raise ValueError(f'Unsupported delivery target "{target_app}".')


def get_reminders_helper_path() -> Path:
	packaged_path: Path = Path(__file__).resolve().parent / "bin" / "reminders-helper.swift"
	if packaged_path.exists():
		return packaged_path

	return Path(__file__).resolve().parents[1] / "bin" / "reminders-helper.swift"
