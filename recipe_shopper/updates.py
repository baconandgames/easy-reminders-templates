from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
	import certifi
except ImportError:
	certifi = None


PACKAGE_NAME: str = "easy-reminder-templates"
GITHUB_REPO_URL: str = "https://github.com/baconandgames/easy-reminders-templates.git"
LATEST_RELEASE_URL: str = "https://api.github.com/repos/baconandgames/easy-reminders-templates/releases/latest"
UPDATE_COMMAND: str = f"pipx upgrade {PACKAGE_NAME}"
GITHUB_ISSUES_URL: str = "https://github.com/baconandgames/easy-reminders-templates/issues/new"
PIPX_BIN_CANDIDATES: tuple[Path, ...] = (
	Path.home() / ".local/bin/pipx",
	Path("/opt/homebrew/bin/pipx"),
	Path("/usr/local/bin/pipx"),
)


@dataclass(frozen=True)
class ReleaseInfo:
	version: str
	name: str
	body: str
	url: str


class UpdateCheckError(Exception):
	"""Raised when release metadata cannot be checked."""


@dataclass(frozen=True)
class UpdateResult:
	success: bool
	command: tuple[str, ...]
	output: str
	error: str = ""


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
	opener: Callable[..., Any] | None = None,
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
		open_url: Callable[..., Any] = opener or open_with_certifi
		with open_url(request, timeout=timeout) as response:
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


def open_with_certifi(request: Request, timeout: float):
	context = ssl.create_default_context(cafile=certifi.where() if certifi is not None else None)
	return urlopen(request, timeout=timeout, context=context)


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


def run_package_update(version: str, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None) -> UpdateResult:
	command: tuple[str, ...] | None = resolve_update_command(version)
	if command is None:
		return UpdateResult(
			success=False,
			command=(),
			output="",
			error=format_unsupported_install_message(),
		)

	try:
		run_command = runner or subprocess.run
		result = run_command(command, capture_output=True, text=True, check=False)
	except OSError as error:
		return UpdateResult(success=False, command=command, output="", error=str(error))

	output = combine_process_output(result.stdout, result.stderr)
	if result.returncode != 0:
		return UpdateResult(success=False, command=command, output=output, error=f"Command exited with {result.returncode}.")

	return UpdateResult(success=True, command=command, output=output)


def resolve_update_command(version: str) -> tuple[str, ...] | None:
	package_spec = format_release_package_spec(version)
	pipx_path: str | None = find_pipx()
	if is_running_from_pipx() and pipx_path is not None:
		return (pipx_path, "install", "--force", "--python", sys.executable, package_spec)

	if is_running_from_project_checkout():
		return None

	if is_running_from_pipx():
		return None

	return (sys.executable, "-m", "pip", "install", "--upgrade", package_spec)


def format_release_package_spec(version: str) -> str:
	return f"git+{GITHUB_REPO_URL}@v{normalize_version(version)}"


def is_running_from_pipx() -> bool:
	executable_path = Path(sys.executable).resolve()
	prefix_path = Path(sys.prefix).resolve()
	return "pipx/venvs" in str(executable_path) or "pipx/venvs" in str(prefix_path)


def is_running_from_project_checkout() -> bool:
	project_file: Path = Path(__file__).resolve().parents[1] / "pyproject.toml"
	git_dir: Path = Path(__file__).resolve().parents[1] / ".git"
	return project_file.exists() and git_dir.exists()


def find_pipx() -> str | None:
	pipx_path: str | None = shutil.which("pipx")
	if pipx_path is not None:
		return pipx_path

	for candidate in PIPX_BIN_CANDIDATES:
		if candidate.exists():
			return str(candidate)

	return None


def combine_process_output(stdout: str, stderr: str) -> str:
	output_parts = [part.strip() for part in (stdout, stderr) if part.strip() != ""]
	return "\n\n".join(output_parts)


def format_unsupported_install_message() -> str:
	return "\n".join(
		[
			"ListKit could not determine a safe automatic update command for this install.",
			"",
			"Manual options:",
			f"- pipx: {UPDATE_COMMAND}",
			f"- pip: {sys.executable} -m pip install --upgrade git+{GITHUB_REPO_URL}@vVERSION",
		]
	)
