from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from src.config import Config
from src.formatter import ShoppingList, format_delivery_item


@dataclass(frozen=True)
class DeliveryResult:
	target_app: str
	target_name: str
	created_items: list[str]
	omitted_items: list[str]
	dry_run: bool


@dataclass(frozen=True)
class DeliveryTargetOption:
	identifier: str
	name: str
	source: str
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
		target_selector: Callable[[str, list[DeliveryTargetOption]], DeliveryTargetOption] | None = None,
	) -> None:
		self._runner = runner
		self._target_selector = target_selector

	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		created_items: list[str] = [format_delivery_item(item) for item in shopping_list.included_items]
		omitted_items: list[str] = [format_delivery_item(item) for item in shopping_list.omitted_items]

		if config.delivery_mode == "create":
			list_identifier: str | None = config.apple_reminders_list_id or self._resolve_list_identifier(config)
			self._run_helper(config, created_items, list_identifier)

		return DeliveryResult(
			target_app=self.target_app,
			target_name=f"{self.target_name}: {config.apple_reminders_list_name}",
			created_items=created_items,
			omitted_items=omitted_items,
			dry_run=config.delivery_mode == "dry_run",
		)

	def list_targets(self) -> list[DeliveryTargetOption]:
		helper_path: Path = Path(__file__).resolve().parents[1] / "bin" / "reminders-helper.swift"
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
				sample_items=[str(item) for item in target.get("sample_items", [])],
			)
			for target in targets
		]

	def _resolve_list_identifier(self, config: Config) -> str:
		matches: list[DeliveryTargetOption] = [
			target for target in self.list_targets() if target.name == config.apple_reminders_list_name
		]

		if len(matches) == 0:
			raise DeliveryError(f"Reminder list not found: {config.apple_reminders_list_name}")

		if len(matches) == 1:
			return matches[0].identifier

		if self._target_selector is None:
			raise DeliveryError(f'Multiple reminder lists named "{config.apple_reminders_list_name}" were found.')

		return self._target_selector(config.apple_reminders_list_name, matches).identifier

	def _run_helper(self, config: Config, created_items: list[str], list_identifier: str | None) -> None:
		helper_path: Path = Path(__file__).resolve().parents[1] / "bin" / "reminders-helper.swift"
		payload: str = json.dumps(
			{
				"listIdentifier": list_identifier,
				"listName": config.apple_reminders_list_name,
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
	target_selector: Callable[[str, list[DeliveryTargetOption]], DeliveryTargetOption] | None = None,
) -> DeliveryTarget:
	if target_app == AppleRemindersTarget.target_app:
		return AppleRemindersTarget(target_selector=target_selector)

	raise ValueError(f'Unsupported delivery target "{target_app}".')
