from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.config import Config
from src.formatter import ShoppingList, format_delivery_item


@dataclass(frozen=True)
class DeliveryResult:
	target_app: str
	target_name: str
	created_parent: str
	created_items: list[str]
	omitted_items: list[str]
	dry_run: bool


class DeliveryTarget(Protocol):
	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		pass


class AppleRemindersTarget:
	target_app: str = "apple_reminders"
	target_name: str = "Apple Reminders"

	def create_list(self, shopping_list: ShoppingList, config: Config) -> DeliveryResult:
		return DeliveryResult(
			target_app=self.target_app,
			target_name=f"{self.target_name}: {config.apple_reminders_list_name}",
			created_parent=shopping_list.recipe_name,
			created_items=[format_delivery_item(item) for item in shopping_list.included_items],
			omitted_items=[format_delivery_item(item) for item in shopping_list.omitted_items],
			dry_run=True,
		)


def get_delivery_target(target_app: str) -> DeliveryTarget:
	if target_app == AppleRemindersTarget.target_app:
		return AppleRemindersTarget()

	raise ValueError(f'Unsupported delivery target "{target_app}".')
