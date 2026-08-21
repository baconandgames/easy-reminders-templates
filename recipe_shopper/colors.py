from __future__ import annotations

import re


NAMED_COLORS: dict[str, str] = {
	"default": "",
	"black": "\033[30m",
	"red": "\033[31m",
	"green": "\033[32m",
	"yellow": "\033[33m",
	"blue": "\033[34m",
	"magenta": "\033[35m",
	"cyan": "\033[36m",
	"white": "\033[37m",
	"grey": "\033[90m",
}
PROMPT_COLORS: dict[str, str] = {
	"default": "",
	"black": "ansiblack",
	"red": "ansired",
	"green": "ansigreen",
	"yellow": "ansiyellow",
	"blue": "ansiblue",
	"magenta": "ansimagenta",
	"cyan": "ansicyan",
	"white": "ansiwhite",
	"grey": "ansibrightblack",
}
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_color(value: str, fallback: str) -> str:
	if value == "default":
		return fallback

	if value in NAMED_COLORS:
		return value

	if HEX_COLOR_PATTERN.match(value):
		return value.lower()

	return fallback


def terminal_color_code(value: str) -> str:
	if value in NAMED_COLORS:
		return NAMED_COLORS[value]

	if HEX_COLOR_PATTERN.match(value):
		red: int = int(value[1:3], 16)
		green: int = int(value[3:5], 16)
		blue: int = int(value[5:7], 16)
		return f"\033[38;2;{red};{green};{blue}m"

	return ""


def prompt_color_style(value: str) -> str:
	if value in PROMPT_COLORS:
		return PROMPT_COLORS[value]

	if HEX_COLOR_PATTERN.match(value):
		return value.lower()

	return ""
