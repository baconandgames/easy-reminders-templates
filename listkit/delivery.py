from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Callable, Protocol

from listkit.config import Config
from listkit.formatter import ShoppingList, format_delivery_item

TargetSelector = Callable[[str, list["DeliveryTargetOption"], int], "DeliveryTargetOption"]
CREATE_NEW_LIST_IDENTIFIER: str = "__create_new_list__"
DEFAULT_COMPLETED_REMINDER_LOOKBACK_DAYS: int = 365
SUGGESTED_COMPLETED_REMINDER_LOOKBACK_DAYS: int = 180
MAX_COMPLETED_REMINDER_SUGGESTIONS: int = 50


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


@dataclass(frozen=True)
class CompletedReminderItem:
	title: str
	completion_date: str | None


@dataclass(frozen=True)
class SuggestedReminderItem:
	title: str
	frequency: int
	recent_count: int
	score: float
	most_recent_completion: str | None


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
		return self._list_targets("list-targets")

	def list_basic_targets(self) -> list[DeliveryTargetOption]:
		return self._list_targets("list-basic-targets")

	def _list_targets(self, command: str) -> list[DeliveryTargetOption]:
		helper_path: Path = get_reminders_helper_path()
		try:
			result = self._runner(
				["swift", str(helper_path), command],
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

	def list_items(self, list_identifier: str) -> list[str]:
		helper_path: Path = get_reminders_helper_path()
		try:
			result = self._runner(
				["swift", str(helper_path), "list-items"],
				input=list_identifier,
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or "Could not list Apple Reminders items."
			raise DeliveryError(message) from error

		try:
			items: list[object] = json.loads(result.stdout)
		except json.JSONDecodeError as error:
			raise DeliveryError("Could not parse Apple Reminders items.") from error

		return [str(item) for item in items]

	def list_completed_items(
		self,
		list_identifier: str,
		days: int | None = DEFAULT_COMPLETED_REMINDER_LOOKBACK_DAYS,
	) -> list[CompletedReminderItem]:
		helper_path: Path = get_reminders_helper_path()
		try:
			result = self._runner(
				["swift", str(helper_path), "list-completed-items"],
				input=json.dumps({"listIdentifier": list_identifier, "days": days}),
				check=True,
				capture_output=True,
				text=True,
			)
		except subprocess.CalledProcessError as error:
			message: str = error.stderr.strip() or "Could not list completed Apple Reminders items."
			raise DeliveryError(message) from error

		try:
			items: list[dict[str, object]] = json.loads(result.stdout)
		except json.JSONDecodeError as error:
			raise DeliveryError("Could not parse completed Apple Reminders items.") from error

		return [
			CompletedReminderItem(
				title=str(item["title"]),
				completion_date=str(item["completion_date"]) if item.get("completion_date") is not None else None,
			)
			for item in items
		]

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


def suggest_completed_reminder_items(
	completed_items: list[CompletedReminderItem],
	existing_items: list[str],
	min_frequency: int = 2,
	limit: int | None = MAX_COMPLETED_REMINDER_SUGGESTIONS,
) -> list[SuggestedReminderItem]:
	existing_keys: set[str] = {_normalize_reminder_title(item) for item in existing_items}
	grouped: dict[str, list[CompletedReminderItem]] = {}
	display_titles: dict[str, str] = {}

	for item in completed_items:
		key: str = _normalize_reminder_title(item.title)
		if not key or key in existing_keys:
			continue
		grouped.setdefault(key, []).append(item)
		display_titles.setdefault(key, item.title.strip())

	suggestions: list[SuggestedReminderItem] = []
	for key, items in grouped.items():
		frequency: int = len(items)
		if frequency < min_frequency:
			continue

		recent_count: int = sum(1 for item in items if _is_recent_completion(item.completion_date))
		most_recent_completion: str | None = max(
			(item.completion_date for item in items if item.completion_date is not None),
			default=None,
		)
		score: float = float(frequency + min(2, recent_count))
		suggestions.append(
			SuggestedReminderItem(
				title=display_titles[key],
				frequency=frequency,
				recent_count=recent_count,
				score=score,
				most_recent_completion=most_recent_completion,
			)
		)

	sorted_suggestions = sorted(
		suggestions,
		key=lambda item: (
			-item.score,
			-item.frequency,
			item.most_recent_completion is None,
			-(datetime.fromisoformat(item.most_recent_completion.replace("Z", "+00:00")).timestamp() if item.most_recent_completion else 0),
			item.title.casefold(),
		),
	)
	if limit is None:
		return sorted_suggestions

	return sorted_suggestions[:limit]


def format_completed_reminder_suggestion(suggestion: SuggestedReminderItem) -> str:
	return f"{suggestion.title} ({suggestion.frequency})"


def default_completed_reminder_suggestion_indexes(suggestions: list[SuggestedReminderItem]) -> set[int]:
	if len(suggestions) == 0:
		return set()

	top_frequency: int = max(suggestion.frequency for suggestion in suggestions)
	frequency_floor: int = max(2, ceil(top_frequency / 2))
	return {
		index
		for index, suggestion in enumerate(suggestions)
		if suggestion.frequency >= frequency_floor
	}


def _normalize_reminder_title(title: str) -> str:
	return " ".join(title.strip().casefold().split())


def _is_recent_completion(completion_date: str | None) -> bool:
	if completion_date is None:
		return False
	try:
		completed_at = datetime.fromisoformat(completion_date.replace("Z", "+00:00"))
	except ValueError:
		return False
	now = datetime.now(completed_at.tzinfo)
	return (now - completed_at).days <= 30
