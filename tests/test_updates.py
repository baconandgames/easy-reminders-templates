from __future__ import annotations

import json

from recipe_shopper.updates import fetch_latest_release, is_newer_version, normalize_version


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
