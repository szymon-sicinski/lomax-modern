"""Tests for presenter settings and the first-run config file.

Every case exercises the config layer added by this card: the modern/authentic
defaults, the JSON schema and its failure modes, and the override rule the CLI
uses.  No game data is involved.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from lomax_modern.config import (
    AUTHENTIC_FILTER,
    AUTHENTIC_SURFACE,
    CONFIG_ENV,
    MODERN_FILTER,
    MODERN_SURFACE,
    SETTINGS_VERSION,
    ConfigError,
    PresentSettings,
    default_config_path,
    load_config,
    load_or_create,
    resolve_settings,
    write_config,
)
from lomax_modern.scaler import Filter


def test_defaults_are_the_modern_experience() -> None:
    settings = PresentSettings()

    assert settings.modern is True
    assert settings.filter is Filter.EPX_AA
    assert settings.surface == (1920, 1080)
    assert settings.scale is None
    assert settings.profile_name == "modern"


def test_config_mapping_is_versioned_and_json_ready() -> None:
    mapping = PresentSettings().to_mapping()

    assert mapping == {
        "version": SETTINGS_VERSION,
        "modern": True,
        "filter": "epx-aa",
        "surface": [1920, 1080],
        "scale": None,
    }
    assert json.loads(json.dumps(mapping)) == mapping


def test_first_run_writes_the_file_and_reports_it(tmp_path: Path) -> None:
    path = tmp_path / "config.json"

    settings, created = load_or_create(path)

    assert created is True
    assert settings == PresentSettings()
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["version"] == SETTINGS_VERSION
    assert on_disk["modern"] is True
    assert on_disk["filter"] == "epx-aa"


def test_second_run_reads_instead_of_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    load_or_create(path)
    write_config(path, PresentSettings(modern=False, filter=Filter.NEAREST))

    settings, created = load_or_create(path)

    assert created is False
    assert settings.modern is False
    assert settings.filter is Filter.NEAREST


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.json"
    original = PresentSettings(
        modern=False,
        filter=Filter.NEAREST,
        surface=(640, 480),
        scale=2,
    )

    write_config(path, original)

    assert load_config(path) == original
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_missing_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.json")


def test_invalid_json_names_the_position(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"version": 1,', encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_config(path)

    message = str(caught.value)
    assert str(path) in message
    assert "invalid JSON" in message
    assert "line 1" in message


def test_unknown_key_is_rejected_not_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = PresentSettings().to_mapping()
    payload["filtre"] = "nearest"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match="filtre"):
        load_config(path)


def test_future_schema_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = PresentSettings().to_mapping()
    payload["version"] = SETTINGS_VERSION + 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match="unsupported config version"):
        load_config(path)


def test_non_object_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON object"):
        load_config(path)


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("modern", "yes", "modern must be true or false"),
        ("filter", "xbrz", "filter must be one of"),
        ("surface", [0, 480], "surface must be two positive ints"),
        ("surface", [640], "exactly two ints"),
        ("surface", "640x480", "surface must be a two-element list"),
        ("surface", [True, 480], "surface must be two positive ints"),
        ("scale", 0, "scale must be >= 1"),
        ("scale", 1.5, "scale must be null"),
    ],
)
def test_invalid_values_are_rejected(
    tmp_path: Path, field: str, value: object, fragment: str
) -> None:
    path = tmp_path / "config.json"
    payload = PresentSettings().to_mapping()
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_config(path)

    assert fragment in str(caught.value)
    assert str(path) in str(caught.value)


def test_missing_fields_fall_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"version": 1, "modern": false}', encoding="utf-8")

    settings = load_config(path)

    assert settings.modern is False
    assert settings.filter is MODERN_FILTER
    assert settings.surface == MODERN_SURFACE


def test_profile_switch_is_a_whole_package() -> None:
    authentic = PresentSettings().with_profile(False)

    assert authentic.modern is False
    assert authentic.filter is AUTHENTIC_FILTER
    assert authentic.surface == AUTHENTIC_SURFACE
    assert authentic.scale is None

    modern = authentic.with_profile(True)
    assert modern.modern is True
    assert modern.filter is MODERN_FILTER
    assert modern.surface == MODERN_SURFACE
    assert modern.scale is None


def test_no_flags_leave_settings_untouched() -> None:
    base = PresentSettings(modern=False, filter=Filter.NEAREST, surface=(640, 480))

    assert resolve_settings(base) == base


def test_toggle_then_explicit_axes() -> None:
    base = PresentSettings(modern=False, filter=Filter.NEAREST, surface=(320, 240))

    modern = resolve_settings(base, modern=True)
    assert modern.modern is True
    assert modern.filter is Filter.EPX_AA
    assert modern.surface == (1920, 1080)

    mixed = resolve_settings(base, modern=True, filter=Filter.NEAREST)
    assert mixed.modern is True
    assert mixed.filter is Filter.NEAREST

    pinned = resolve_settings(base, modern=True, surface=(640, 480), scale=2)
    assert pinned.surface == (640, 480)
    assert pinned.scale == 2


def test_scale_auto_resets_a_pinned_factor() -> None:
    base = PresentSettings(scale=3)

    assert resolve_settings(base, scale="auto").scale is None
    assert resolve_settings(base, scale=2).scale == 2
    # Not passing --scale keeps the stored value.
    assert resolve_settings(base).scale == 3


def test_config_path_env_override(tmp_path: Path) -> None:
    explicit = tmp_path / "portable.json"

    assert default_config_path({CONFIG_ENV: str(explicit)}) == explicit


def test_config_path_follows_xdg(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}

    assert (
        default_config_path(env)
        == tmp_path / "xdg" / "lomax-modern" / "config.json"
    )


def test_config_path_defaults_to_dot_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert (
        default_config_path({})
        == tmp_path / ".config" / "lomax-modern" / "config.json"
    )


def test_config_path_follows_appdata_on_windows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    env = {"APPDATA": str(tmp_path / "roaming")}

    assert (
        default_config_path(env)
        == tmp_path / "roaming" / "lomax-modern" / "config.json"
    )


def test_config_never_contains_a_file_digest(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    write_config(path, PresentSettings())

    text = path.read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-f]{64}", text)
