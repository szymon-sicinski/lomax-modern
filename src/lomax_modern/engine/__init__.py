"""Engine core — the simulation half of the own-engine vertical slice.

This package turns the byte-exact ``wld`` container and the ``art`` decode into
a playable world: a map/collision grid, a fixed 60 Hz tick, player/entity
state, and a 16-bit ``B5G6R5`` frame.  It is deliberately dependency-free
Python (see ``docs/architecture.md`` §5); the C presenter/renderer is a
separate ``native/`` component owned by the M4 card.

Nothing here reads the original executable, and nothing here interprets a data
field beyond what is measured in ``docs/file-formats.md``.  Unknowns are carried
verbatim and flagged, never guessed.
"""

from .entities import Collectible, Exit, Input, Player
from .level import (
    CELL_PX,
    CollisionModel,
    Level,
    load_clip_table,
    load_level,
    load_player_sprite,
)
from .render import (
    Frame,
    MarkerStyle,
    camera,
    frame_to_rgba,
    gnmy_marker,
    overlay_gnmy,
    pack_rgb565,
    render,
    render_tiles,
)
from .state import GameState, Snapshot, new_game_state, select_clip, step_player
from .run import SliceReport, run_slice

__all__ = [
    "CELL_PX",
    "CollisionModel",
    "Collectible",
    "Exit",
    "Frame",
    "GameState",
    "Input",
    "Level",
    "MarkerStyle",
    "Player",
    "SliceReport",
    "Snapshot",
    "camera",
    "frame_to_rgba",
    "gnmy_marker",
    "load_clip_table",
    "load_level",
    "load_player_sprite",
    "new_game_state",
    "overlay_gnmy",
    "pack_rgb565",
    "render",
    "render_tiles",
    "run_slice",
    "select_clip",
    "step_player",
]
