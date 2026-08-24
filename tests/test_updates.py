from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from listkit.updates import (
	PACKAGE_NAME,
	fetch_latest_release,
	get_current_version,
	is_newer_version,
	normalize_version,
	resolve_update_command,
	run_package_update,
)


class FakeResponse:
	def __init__(self, data: dict[str, object]) -> None:
		self.data = data

	def __enter__(self):
		return self

	def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
		return None

	def read(self) -> bytes:
		return json.dumps(self.data).encode("utf-8")


def test_normalize_version_strips_leading_v() -> None:
	assert normalize_version("v0.1.5") == "0.1.5"


def test_is_newer_version_compares_version_parts() -> None:
	assert is_newer_version("0.1.5", "0.1.4") is True
	assert is_newer_version("0.1.4", "0.1.4") is False
	assert is_newer_version("0.1.4", "0.1.5") is False


def test_fetch_latest_release_reads_github_release_payload() -> None:
	def fake_opener(_request, timeout):
		assert timeout == 3
		return FakeResponse(
			{
				"tag_name": "v0.1.5",
				"name": "Beta polish",
				"body": "Release notes",
				"html_url": "https://github.com/example/release",
			}
		)

	release = fetch_latest_release(opener=fake_opener)

	assert release.version == "0.1.5"
	assert release.name == "Beta polish"
	assert release.body == "Release notes"
	assert release.url == "https://github.com/example/release"


def test_get_current_version_reads_project_version() -> None:
	project_data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

	assert get_current_version() == project_data["project"]["version"]


def test_resolve_update_command_uses_pipx_when_running_from_pipx(monkeypatch) -> None:
	monkeypatch.setattr("listkit.updates.is_running_from_pipx", lambda: True)
	monkeypatch.setattr("listkit.updates.is_running_from_project_checkout", lambda: False)
	monkeypatch.setattr("listkit.updates.find_pipx", lambda: "/opt/homebrew/bin/pipx")

	assert resolve_update_command("0.4.1") == (
		"/opt/homebrew/bin/pipx",
		"install",
		"--force",
		"--python",
		sys.executable,
		"git+https://github.com/baconandgames/listkit.git@v0.4.1",
	)


def test_resolve_update_command_uses_pip_for_non_project_install(monkeypatch) -> None:
	monkeypatch.setattr("listkit.updates.is_running_from_pipx", lambda: False)
	monkeypatch.setattr("listkit.updates.is_running_from_project_checkout", lambda: False)

	assert resolve_update_command("0.4.1") == (
		sys.executable,
		"-m",
		"pip",
		"install",
		"--upgrade",
		"git+https://github.com/baconandgames/listkit.git@v0.4.1",
	)


def test_resolve_update_command_rejects_project_checkout(monkeypatch) -> None:
	monkeypatch.setattr("listkit.updates.is_running_from_pipx", lambda: False)
	monkeypatch.setattr("listkit.updates.is_running_from_project_checkout", lambda: True)

	assert resolve_update_command("0.4.1") is None


def test_run_package_update_captures_failed_output(monkeypatch) -> None:
	def fake_runner(command, capture_output, text, check):
		assert capture_output is True
		assert text is True
		assert check is False
		return subprocess.CompletedProcess(command, 1, stdout="stdout text", stderr="stderr text")

	monkeypatch.setattr("listkit.updates.resolve_update_command", lambda version: ("pipx", "upgrade", PACKAGE_NAME))

	result = run_package_update("0.4.1", runner=fake_runner)

	assert result.success is False
	assert result.command == ("pipx", "upgrade", PACKAGE_NAME)
	assert "stdout text" in result.output
	assert "stderr text" in result.output
	assert result.error == "Command exited with 1."
