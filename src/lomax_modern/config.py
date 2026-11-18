"""Presenter settings and the config file written on first run.

The product stance (``docs/roadmap/15-strategy-report.md`` §7) is
**quality-of-life first**: the modern experience is the default and
authenticity is an opt-in toggle.  This module owns the persistence half of
that stance — the defaults, the file format, where the file lives, and the rule
for how a command-line flag overrides a stored value.

What "modern" and "authentic" mean *here* (M4 scope, no art invention):

===========  ==================================  =============================
Aspect       Modern default                      Authentic toggle
===========  ==================================  =============================
Surface      1920x1080, content integer-scaled   native 320x240, scale 1
Filter       ``epx-aa`` (edge-directed AA)       ``nearest``
Tick rate    engine's fixed 60 Hz                 engine's fixed 60 Hz
===========  ==================================  =============================

Internal render resolution is unchanged at 320x240: HD/framebuffer work is M9,
not a config flag.  The audio, input and save-state rows of the strategy table
belong to their own milestones and are deliberately absent.

The file is plain JSON with an explicit ``version`` so a future presenter can
reject an unknown schema instead of half-reading it.  Unknown keys are an
error, not a warning: a silently ignored ``filtre`` is a setting that never
takes effect, which is exactly the class of bug this module exists to prevent.

Nothing here touches game data.  The only write is the config file, and only
when it does not exist yet or when the caller asks to save.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .scaler import Filter

__all__ = [
    "AUTHENTIC_FILTER",
    "AUTHENTIC_SURFACE",
    "CONFIG_ENV",
    "ConfigError",
    "DEFAULT_CONFIG_FILENAME",
    "MODERN_FILTER",
    "MODERN_SURFACE",
    "PresentSettings",
    "SETTINGS_VERSION",
    "UNSET",
    "default_config_path",
    "load_config",
    "load_or_create",
    "resolve_settings",
    "write_config",
]

#: Schema version of the config file.  Bumped only on an incompatible change.
SETTINGS_VERSION = 1

#: Environment variable that overrides the config location (mostly for tests and
#: for a portable/roaming install).
CONFIG_ENV = "LOMAX_CONFIG"

#: Directory name under the platform config root.
DEFAULT_CONFIG_FILENAME = "config.json"

#: Modern profile: a 16:9 surface; 320x240 content fits at 4x, pillarboxed.
MODERN_SURFACE: tuple[int, int] = (1920, 1080)

#: Authentic profile: the original internal resolution, one screen pixel per
#: source pixel.
AUTHENTIC_SURFACE: tuple[int, int] = (320, 240)

MODERN_FILTER = Filter.EPX_AA
AUTHENTIC_FILTER = Filter.NEAREST

#: Marks "leave this setting alone" in :func:`resolve_settings`, so an explicit
#: ``scale = None`` (auto) is distinguishable from "no ``--scale`` flag".
UNSET = object()


class ConfigError(ValueError):
    """The config file is missing, unreadable, or violates the schema."""


def _is_int(value: Any) -> bool:
    """True for an integer that is not a ``bool`` (``bool`` is an ``int``)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _describe(value: Any) -> str:
    return f"{value!r} ({type(value).__name__})"


def _normalise_surface(value: Any) -> tuple[int, int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ConfigError(
            f"surface must be a two-element list of positive ints, got {_describe(value)}"
        )
    if len(value) != 2:
        raise ConfigError(
            f"surface must hold exactly two ints (width, height), got {len(value)} values"
        )
    width, height = value
    if not (_is_int(width) and _is_int(height)) or width < 1 or height < 1:
        raise ConfigError(
            f"surface must be two positive ints (width, height), got {value!r}"
        )
    return (width, height)


@dataclass(frozen=True, slots=True)
class PresentSettings:
    """Everything ``present`` needs to choose a look, all validated.

    ``scale = None`` means *auto*: the largest integer factor that fits the
    surface.  A positive int pins the factor for this run; :func:`plan_settings`
    (in :mod:`lomax_modern.presenter`) refuses one that does not fit rather
    than silently shrinking it.
    """

    modern: bool = True
    filter: Filter | str = MODERN_FILTER
    surface: tuple[int, int] | list[int] = MODERN_SURFACE
    scale: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.modern, bool):
            raise ConfigError(f"modern must be true or false, got {_describe(self.modern)}")
        try:
            chosen = Filter(self.filter)
        except ValueError:
            valid = ", ".join(item.value for item in Filter)
            raise ConfigError(
                f"filter must be one of {valid}, got {self.filter!r}"
            ) from None
        object.__setattr__(self, "filter", chosen)
        object.__setattr__(self, "surface", _normalise_surface(self.surface))
        if self.scale is not None:
            if not _is_int(self.scale):
                raise ConfigError(
                    f"scale must be null (auto) or a positive int, got {_describe(self.scale)}"
                )
            if self.scale < 1:
                raise ConfigError(f"scale must be >= 1, got {self.scale}")

    # -- presentation -----------------------------------------------------

    @property
    def profile_name(self) -> str:
        return "modern" if self.modern else "authentic"

    def with_profile(self, modern: bool) -> "PresentSettings":
        """Return the coherent settings package for the modern/authentic toggle.

        The toggle is a *profile*, not a lone boolean: authentic means native
        320x240, nearest-neighbour and auto scale; modern means the widescreen
        surface, the high-quality filter and auto scale.  Individual axes can
        still be overridden afterwards by an explicit flag — the report says
        which choice came from where.
        """
        if modern:
            return replace(
                self,
                modern=True,
                filter=MODERN_FILTER,
                surface=MODERN_SURFACE,
                scale=None,
            )
        return replace(
            self,
            modern=False,
            filter=AUTHENTIC_FILTER,
            surface=AUTHENTIC_SURFACE,
            scale=None,
        )

    # -- serialisation ----------------------------------------------------

    def to_mapping(self) -> dict[str, Any]:
        """The JSON-ready form, with an explicit schema version."""
        return {
            "version": SETTINGS_VERSION,
            "modern": self.modern,
            "filter": self.filter.value,
            "surface": [self.surface[0], self.surface[1]],
            "scale": self.scale,
        }

    @classmethod
    def from_mapping(
        cls, data: Any, *, source: str | Path | None = None
    ) -> "PresentSettings":
        """Validate a decoded config mapping, with ``source`` in every error."""
        prefix = f"{source}: " if source is not None else ""
        if not isinstance(data, Mapping):
            raise ConfigError(
                f"{prefix}config must be a JSON object, got {_describe(data)}"
            )
        known = {"version", "modern", "filter", "surface", "scale"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ConfigError(
                f"{prefix}unknown config key(s): {', '.join(unknown)}; "
                f"known keys are {', '.join(sorted(known))}"
            )

        version = data.get("version", SETTINGS_VERSION)
        if not _is_int(version):
            raise ConfigError(f"{prefix}version must be an int, got {_describe(version)}")
        if version != SETTINGS_VERSION:
            raise ConfigError(
                f"{prefix}unsupported config version {version}; this build writes "
                f"version {SETTINGS_VERSION}"
            )

        fields = {key: data[key] for key in ("modern", "filter", "surface", "scale") if key in data}
        try:
            return cls(**fields)
        except ConfigError as exc:
            raise ConfigError(f"{prefix}{exc}") from None


def resolve_settings(
    base: PresentSettings,
    *,
    modern: bool | None = None,
    filter: Filter | str | None = None,
    surface: tuple[int, int] | None = None,
    scale: int | str | None | object = UNSET,
) -> PresentSettings:
    """Apply command-line overrides to stored settings.

    ``None`` means "no flag" for every argument; ``scale`` needs the
    :data:`UNSET` sentinel because ``None`` is itself a legal value (auto).
    ``scale="auto"`` resets a pinned factor back to auto.  Profile flags are
    applied first, then the explicit per-axis flags, so ``--authentic --filter
    epx-aa`` is a deliberate (reported) mix rather than a contradiction.
    """
    settings = base.with_profile(modern) if modern is not None else base
    changes: dict[str, Any] = {}
    if filter is not None:
        changes["filter"] = filter
    if surface is not None:
        changes["surface"] = surface
    if scale is not UNSET:
        if scale is None or (isinstance(scale, str) and scale.casefold() == "auto"):
            changes["scale"] = None
        else:
            changes["scale"] = scale
    return replace(settings, **changes) if changes else settings


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Where the config lives when ``--config`` is not given.

    ``$LOMAX_CONFIG`` wins outright; otherwise the platform convention:
    ``%APPDATA%`` on Windows, ``~/Library/Application Support`` on macOS and
    ``$XDG_CONFIG_HOME`` (default ``~/.config``) everywhere else.
    """
    env = os.environ if env is None else env
    explicit = env.get(CONFIG_ENV)
    if explicit:
        return Path(explicit).expanduser()

    if sys.platform == "win32":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "lomax-modern" / DEFAULT_CONFIG_FILENAME
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "lomax-modern"
            / DEFAULT_CONFIG_FILENAME
        )
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "lomax-modern" / DEFAULT_CONFIG_FILENAME


def load_config(path: str | Path) -> PresentSettings:
    """Read and validate a config file; every failure is a :class:`ConfigError`."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{path}: config file not found") from None
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read config ({exc.strerror or exc})") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{path}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}"
        ) from None
    return PresentSettings.from_mapping(data, source=path)


def write_config(path: str | Path, settings: PresentSettings) -> None:
    """Write ``settings`` atomically, creating parent directories as needed.

    A half-written config is worse than none: it would make the next run fail
    with a parse error and no way back.  The file is therefore staged in the
    target directory and moved into place with :func:`os.replace`.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings.to_mapping(), indent=2) + "\n"
        fd, staged = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
    except OSError as exc:
        raise ConfigError(f"{path}: cannot create config directory ({exc})") from None

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, path)
    except OSError as exc:
        try:
            os.unlink(staged)
        except OSError:
            pass
        raise ConfigError(f"{path}: cannot write config ({exc})") from None


def load_or_create(path: str | Path) -> tuple[PresentSettings, bool]:
    """Load the config, writing the modern defaults if the file is absent.

    Returns ``(settings, created)`` so the caller can tell the user that the
    file was written on this run — "where did this file come from" is otherwise
    a support question.
    """
    path = Path(path)
    if path.exists():
        return load_config(path), False
    settings = PresentSettings()
    write_config(path, settings)
    return settings, True
