from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PACKAGE_NAME: str = "easy-reminder-templates"
LATEST_RELEASE_URL: str = "https://api.github.com/repos/baconandgames/easy-reminders-templates/releases/latest"
UPDATE_COMMAND: str = f"pipx upgrade {PACKAGE_NAME}"


@dataclass(frozen=True)
class ReleaseInfo:
	version: str
	name: str
	body: str
	url: str


class UpdateCheckError(Exception):
	"""Raised when release metadata cannot be checked."""


def get_current_version() -> str:
	project_version: str | None = read_project_version()
	if project_version is not None:
		return project_version

	try:
		return version(PACKAGE_NAME)
	except PackageNotFoundError:
		return "0.0.0"


def read_project_version() -> str | None:
	project_file: Path = Path(__file__).resolve().parents[1] / "pyproject.toml"
	if not project_file.exists():
		return None

	try:
		project_data: Any = tomllib.loads(project_file.read_text(encoding="utf-8"))
	except (OSError, tomllib.TOMLDecodeError):
		return None

	project: Any = project_data.get("project")
	if not isinstance(project, dict):
		return None

	project_version: Any = project.get("version")
	if not isinstance(project_version, str) or project_version.strip() == "":
		return None

	return project_version


def fetch_latest_release(
	release_url: str = LATEST_RELEASE_URL,
	opener: Callable[..., Any] = urlopen,
	timeout: float = 3,
) -> ReleaseInfo:
	request = Request(
		release_url,
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": "easy-reminder-templates",
		},
	)
	try:
		with opener(request, timeout=timeout) as response:
			raw_data: Any = json.loads(response.read().decode("utf-8"))
	except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
		raise UpdateCheckError(f"Could not check GitHub releases: {error}") from error

	if not isinstance(raw_data, dict):
		raise UpdateCheckError("GitHub release response was not a JSON object.")

	tag_name: Any = raw_data.get("tag_name", "")
	if not isinstance(tag_name, str) or tag_name.strip() == "":
		raise UpdateCheckError("GitHub release response did not include a tag name.")

	name: Any = raw_data.get("name", tag_name)
	body: Any = raw_data.get("body", "")
	html_url: Any = raw_data.get("html_url", "")
	return ReleaseInfo(
		version=normalize_version(tag_name),
		name=name if isinstance(name, str) else tag_name,
		body=body if isinstance(body, str) else "",
		url=html_url if isinstance(html_url, str) else "",
	)


def normalize_version(value: str) -> str:
	return value.strip().removeprefix("v").removeprefix("V")


def is_newer_version(candidate: str, current: str) -> bool:
	return parse_version_parts(candidate) > parse_version_parts(current)


def parse_version_parts(value: str) -> tuple[int, ...]:
	parts: list[int] = []
	for part in normalize_version(value).split("."):
		digits: list[str] = []
		for character in part:
			if not character.isdigit():
				break
			digits.append(character)
		parts.append(int("".join(digits) or "0"))

	return tuple(parts)
