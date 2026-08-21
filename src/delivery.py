from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol

from src.config import Config
from src.formatter import ShoppingList, format_delivery_item


@dataclass(frozen=True)
class DeliveryResult:
	target_app: str
	target_name: str
	created_items: list[str]
	omitted_items: list[str]
	dry_run: bool


class DeliveryError(Exception):
	"""Raised when delivery to a target app fails."""


class DeliveryTarget(Protocol):
	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		pass


class AppleRemindersTarget:
	target_app: str = "apple_reminders"
	target_name: str = "Apple Reminders"

	def __init__(self, runner=subprocess.run) -> None:
		self._runner = runner

	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		created_items: list[str] = [format_delivery_item(item) for item in shopping_list.included_items]
		omitted_items: list[str] = [format_delivery_item(item) for item in shopping_list.omitted_items]

		if config.delivery_mode == "create":
			self._run_script(build_apple_reminders_script(config.apple_reminders_list_name, created_items))

		return DeliveryResult(
			target_app=self.target_app,
			target_name=f"{self.target_name}: {config.apple_reminders_list_name}",
			created_items=created_items,
			omitted_items=omitted_items,
			dry_run=config.delivery_mode == "dry_run",
		)

	def _run_script(self, script: str) -> None:
		try:
			self._runner(
				["osascript", "-e", script],
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or "Apple Reminders delivery failed."
			raise DeliveryError(message) from error


def get_delivery_target(target_app: str) -> DeliveryTarget:
	if target_app == AppleRemindersTarget.target_app:
		return AppleRemindersTarget()

	raise ValueError(f'Unsupported delivery target "{target_app}".')


def build_apple_reminders_script(list_name: str, item_names: list[str]) -> str:
	lines: list[str] = [
		'tell application "Reminders"',
		f"set targetList to list {quote_applescript_string(list_name)}",
	]

	for item_name in item_names:
		lines.append(
			f"make new reminder at end of reminders of targetList with properties {{name:{quote_applescript_string(item_name)}}}"
		)

	lines.append("end tell")
	return "\n".join(lines)


def quote_applescript_string(value: str) -> str:
	escaped: str = value.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}"'
