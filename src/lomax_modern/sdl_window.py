"""SDL2 window backend: show a 16-bit ``B5G6R5`` frame, paced at 60 Hz.

This is the presentation half of demo option **C-animated**
(``docs/roadmap/43-demo-plan.md`` §6.1; ``docs/roadmap/44-presenter-options.md``
§1.1 picks **ctypes + SDL2** as the default).  It opens a window at the
configured surface, uploads a 320x240 ``B5G6R5`` buffer to an
``SDL_PIXELFORMAT_RGB565`` streaming texture, and lets SDL2 do the
integer-scale blit to the letterboxed destination rectangle.

The per-frame path is SDL2-native, **never** ``scaler.nearest`` or
``scaler.epx_aa``: those cost ~40 ms / ~142 ms per 4x frame while the SDL2 blit
is ~1.18 ms against a 16.67 ms budget (measured, ``44-presenter-options.md``
§2).  Only ``scaler.fit_scale`` is imported, for the *geometry* (integer
factor + offsets), and only once at open time — it never runs per frame.

SDL2 is a *system* library located with ``ctypes.util.find_library("SDL2")``,
so ``pyproject.toml`` keeps ``dependencies = []``.  When it is absent the entry
point prints one line and exits 1 instead of raising a traceback.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import struct
import sys
import time
from dataclasses import dataclass
from typing import Callable, Iterator

from . import scaler

__all__ = [
    "MISSING_SDL2_MESSAGE",
    "SDL2Error",
    "SDL2MissingError",
    "Window",
    "load_sdl2",
    "open_window",
    "plan_layout",
]

#: The one line printed (and exit 1) when SDL2 is not installed.
MISSING_SDL2_MESSAGE = "install libsdl2 (e.g. apt install libsdl2-2.0-0)"

#: Window title used when the caller does not pass one.
DEFAULT_TITLE = "lomax-modern"

#: Frames the standalone ``open_window(size, size)`` runs before closing, so the
#: loop terminates with no input (and no display, under the dummy driver).
DEFAULT_MAX_FRAMES = 60

# --- SDL2 constants (``SDL_video.h`` / ``SDL_render.h`` / ``SDL_events.h``) --

SDL_INIT_VIDEO = 0x00000020
SDL_WINDOW_SHOWN = 0x00000004
SDL_WINDOWPOS_CENTERED = 0x2FFF0000
SDL_RENDERER_SOFTWARE = 0x00000001
SDL_RENDERER_ACCELERATED = 0x00000002
SDL_TEXTUREACCESS_STREAMING = 1

#: ``SDL_DEFINE_PIXELFORMAT(SDL_PIXELTYPE_PACKED16, SDL_PACKEDORDER_XRGB,
#: SDL_PACKEDLAYOUT_565, 16, 2)`` == 0x15151002.  ``B5G6R5``: the same word
#: layout as :func:`lomax_modern.engine.render.pack_rgb565`.
SDL_PIXELFORMAT_RGB565 = 0x15151002

SDL_QUIT = 0x100
SDL_KEYDOWN = 0x300
SDLK_ESCAPE = 0x1B

#: ``SDL_Event`` is a fixed 56-byte union (compile-time asserted in SDL2).
_SDL_EVENT_SIZE = 56
#: ``SDL_KeyboardEvent.keysym.sym``: type(4)+timestamp(4)+windowID(4)+
#: state/repeat/padding(4) = 16, then ``SDL_Keysym`` scancode(4) -> sym at 20.
_KEY_SYM_OFFSET = 20


class SDL2Error(RuntimeError):
    """An SDL2 call failed; ``str`` carries ``SDL_GetError``."""


class SDL2MissingError(RuntimeError):
    """SDL2 is not installed; ``str`` is the one-line install hint."""


def _find_sdl2() -> str | None:
    """The SDL2 shared library name, or ``None`` when it is not installed."""
    return ctypes.util.find_library("SDL2")


class _SDL2:
    """A thin ctypes binding to the SDL2 entry points this backend uses.

    Every method raises :class:`SDL2Error` (with ``SDL_GetError``) on failure,
    so callers never have to translate raw SDL return codes.  Creation calls
    return the opaque handle; ``SDL_QUIT``/cleanup are explicit methods.
    """

    def __init__(self, libname: str) -> None:
        self._lib = ctypes.CDLL(libname)
        self._bind()

    def _bind(self) -> None:
        lib = self._lib
        lib.SDL_Init.argtypes = [ctypes.c_uint32]
        lib.SDL_Init.restype = ctypes.c_int
        lib.SDL_CreateWindow.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        lib.SDL_CreateWindow.restype = ctypes.c_void_p
        lib.SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
        lib.SDL_CreateRenderer.restype = ctypes.c_void_p
        lib.SDL_CreateTexture.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.SDL_CreateTexture.restype = ctypes.c_void_p
        lib.SDL_UpdateTexture.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        lib.SDL_UpdateTexture.restype = ctypes.c_int
        lib.SDL_RenderClear.argtypes = [ctypes.c_void_p]
        lib.SDL_RenderClear.restype = ctypes.c_int
        lib.SDL_RenderCopy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.SDL_RenderCopy.restype = ctypes.c_int
        lib.SDL_RenderPresent.argtypes = [ctypes.c_void_p]
        lib.SDL_RenderPresent.restype = None
        lib.SDL_PollEvent.argtypes = [ctypes.c_void_p]
        lib.SDL_PollEvent.restype = ctypes.c_int
        lib.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.SDL_SetHint.restype = ctypes.c_int
        lib.SDL_SetWindowTitle.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.SDL_SetWindowTitle.restype = None
        lib.SDL_PixelFormatEnumToMasks.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        lib.SDL_PixelFormatEnumToMasks.restype = ctypes.c_int
        lib.SDL_DestroyTexture.argtypes = [ctypes.c_void_p]
        lib.SDL_DestroyTexture.restype = None
        lib.SDL_DestroyRenderer.argtypes = [ctypes.c_void_p]
        lib.SDL_DestroyRenderer.restype = None
        lib.SDL_DestroyWindow.argtypes = [ctypes.c_void_p]
        lib.SDL_DestroyWindow.restype = None
        lib.SDL_Quit.argtypes = []
        lib.SDL_Quit.restype = None
        lib.SDL_GetError.argtypes = []
        lib.SDL_GetError.restype = ctypes.c_char_p

    # -- error / lifecycle ---------------------------------------------------

    def error(self) -> str:
        message = self._lib.SDL_GetError()
        return message.decode("utf-8", "replace") if message else "unknown SDL2 error"

    def _check(self, name: str, rc: int) -> None:
        if rc != 0:
            raise SDL2Error(f"{name}: {self.error()}")

    def init_video(self) -> None:
        self._check("SDL_Init", self._lib.SDL_Init(SDL_INIT_VIDEO))

    def set_scale_quality_nearest(self) -> None:
        # Nearest for integer factors is exact block replication (no shimmer).
        self._lib.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"nearest")

    def quit(self) -> None:
        self._lib.SDL_Quit()

    # -- creation ------------------------------------------------------------

    def create_window(self, title: str, width: int, height: int) -> int:
        handle = self._lib.SDL_CreateWindow(
            title.encode("utf-8"),
            SDL_WINDOWPOS_CENTERED,
            SDL_WINDOWPOS_CENTERED,
            width,
            height,
            SDL_WINDOW_SHOWN,
        )
        if not handle:
            raise SDL2Error(f"SDL_CreateWindow: {self.error()}")
        return handle

    def create_renderer(self, window: int) -> int:
        handle = self._lib.SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED)
        if not handle:
            handle = self._lib.SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE)
        if not handle:
            raise SDL2Error(f"SDL_CreateRenderer: {self.error()}")
        return handle

    def create_texture(self, renderer: int, pixel_format: int, width: int, height: int) -> int:
        handle = self._lib.SDL_CreateTexture(
            renderer, pixel_format, SDL_TEXTUREACCESS_STREAMING, width, height
        )
        if not handle:
            raise SDL2Error(f"SDL_CreateTexture: {self.error()}")
        return handle

    # -- per-frame -----------------------------------------------------------

    def update_texture(self, texture: int, pixels: object, pitch: int) -> None:
        self._check("SDL_UpdateTexture", self._lib.SDL_UpdateTexture(texture, None, pixels, pitch))

    def render_clear(self, renderer: int) -> None:
        self._check("SDL_RenderClear", self._lib.SDL_RenderClear(renderer))

    def render_copy(self, renderer: int, texture: int, dst_rect: "SDL_Rect") -> None:
        self._check(
            "SDL_RenderCopy",
            self._lib.SDL_RenderCopy(renderer, texture, None, ctypes.byref(dst_rect)),
        )

    def render_present(self, renderer: int) -> None:
        self._lib.SDL_RenderPresent(renderer)

    def poll_event(self, event_buf: object) -> int:
        return self._lib.SDL_PollEvent(event_buf)

    def set_window_title(self, window: int, title: str) -> None:
        self._lib.SDL_SetWindowTitle(window, title.encode("utf-8"))

    def pixel_format_masks(self, pixel_format: int) -> tuple[int, int, int, int, int]:
        """``(bpp, rmask, gmask, bmask, amask)`` for a pixel format enum value."""
        bpp = ctypes.c_int()
        rmask = ctypes.c_uint32()
        gmask = ctypes.c_uint32()
        bmask = ctypes.c_uint32()
        amask = ctypes.c_uint32()
        ok = self._lib.SDL_PixelFormatEnumToMasks(
            pixel_format,
            ctypes.byref(bpp),
            ctypes.byref(rmask),
            ctypes.byref(gmask),
            ctypes.byref(bmask),
            ctypes.byref(amask),
        )
        if not ok:
            raise SDL2Error(f"SDL_PixelFormatEnumToMasks(0x{pixel_format:08x}): {self.error()}")
        return bpp.value, rmask.value, gmask.value, bmask.value, amask.value

    # -- teardown ------------------------------------------------------------

    def destroy_texture(self, texture: int) -> None:
        if texture:
            self._lib.SDL_DestroyTexture(texture)

    def destroy_renderer(self, renderer: int) -> None:
        if renderer:
            self._lib.SDL_DestroyRenderer(renderer)

    def destroy_window(self, window: int) -> None:
        if window:
            self._lib.SDL_DestroyWindow(window)


class SDL_Rect(ctypes.Structure):
    """``SDL_Rect`` as SDL expects it (x, y, w, h, all ``int``)."""

    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("w", ctypes.c_int),
        ("h", ctypes.c_int),
    ]


def load_sdl2(finder: Callable[[], str | None] = _find_sdl2) -> _SDL2:
    """Load the SDL2 library, or raise :class:`SDL2MissingError` when absent.

    ``finder`` is injectable so the missing-library path is unit-testable
    without uninstalling SDL2.
    """
    name = finder()
    if name is None:
        raise SDL2MissingError(MISSING_SDL2_MESSAGE)
    return _SDL2(name)


@dataclass(frozen=True)
class Layout:
    """Destination rectangle for the integer-scaled content on the surface."""

    scale: int
    x: int
    y: int
    width: int
    height: int


def plan_layout(
    source_size: tuple[int, int], surface_size: tuple[int, int]
) -> Layout:
    """Integer fit + letterbox geometry for one source frame on one surface.

    Reuses :func:`scaler.fit_scale` (pure, unit-tested) for the geometry only;
    the actual pixel scaling is SDL2's, never ``scaler.nearest``/``epx_aa``.
    """
    fit = scaler.fit_scale(
        source_size[0], source_size[1], surface_size[0], surface_size[1]
    )
    return Layout(
        scale=fit.scale,
        x=fit.offset_x,
        y=fit.offset_y,
        width=fit.content_width,
        height=fit.content_height,
    )


def _decode_event(raw: bytes) -> tuple[int, int]:
    """``(event_type, key_sym)`` from a 56-byte ``SDL_Event``.

    ``key_sym`` is only meaningful for ``SDL_KEYDOWN``/``SDL_KEYUP``; it is
    returned regardless so callers can decide.
    """
    event_type = struct.unpack_from("<I", raw, 0)[0]
    key_sym = struct.unpack_from("<i", raw, _KEY_SYM_OFFSET)[0]
    return event_type, key_sym


def _sleep_to(tick_start: float, interval: float) -> None:
    """Sleep until ``interval`` has elapsed since ``tick_start``.

    A fixed 60 Hz pacing that sleeps the *remaining* budget rather than a busy
    spin; when a frame already overran the interval it returns immediately.
    """
    remaining = interval - (time.monotonic() - tick_start)
    if remaining > 0:
        time.sleep(remaining)


def _frame_bytes(frame: object, expected: int) -> bytes:
    """Coerce a frame to exactly ``expected`` bytes of ``B5G6R5`` LE words.

    Accepts ``bytes``/``bytearray`` or any object exposing ``to_bytes()`` (an
    :class:`lomax_modern.engine.Frame` does).  A wrong length is an error, not
    a silently truncated upload.
    """
    if isinstance(frame, (bytes, bytearray)):
        data = bytes(frame)
    else:
        # ``int`` has an unrelated ``to_bytes(length, byteorder)``; guard the
        # plain scalars out so duck-typing never reaches a wrong method.
        if isinstance(frame, (str, int, float, bool)) or frame is None:
            raise TypeError(
                f"frame must be bytes or expose to_bytes(), got {type(frame).__name__}"
            )
        to_bytes = getattr(frame, "to_bytes", None)
        if not callable(to_bytes):
            raise TypeError(
                f"frame must be bytes or expose to_bytes(), got {type(frame).__name__}"
            )
        data = to_bytes()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("frame.to_bytes() must return bytes")
        data = bytes(data)
    if len(data) != expected:
        raise ValueError(f"frame is {len(data)} bytes; expected {expected}")
    return data


def _synthetic_frames(source_size: tuple[int, int]) -> Iterator[bytes]:
    """An endless animated test pattern (a sweeping bar), no game data.

    Used only when ``open_window`` is called without a frame source, so the
    standalone ``open_window(size, size)`` check visibly animates and then
    stops on its own.
    """
    width, height = source_size
    count = width * height
    sky = scaler.pack_rgb565(2, 3, 6)  # dark blue
    bar = scaler.pack_rgb565(31, 55, 0)  # bright yellow
    x = 0
    while True:
        pixels = [sky] * count
        bar_cols = min(8, width)
        for row in range(height):
            for col in range(bar_cols):
                px = (x + col) % width
                pixels[row * width + px] = bar
        yield struct.pack("<" + "H" * count, *pixels)
        x = (x + 2) % width


class Window:
    """An open SDL2 window + ``RGB565`` texture, ready to present frames.

    ``Window`` is the push-style building block the ``window`` command (card B)
    drives from ``run_slice``'s ``on_frame`` sink; :func:`open_window` is the
    pull-style convenience wrapper that the headless check exercises directly.
    """

    def __init__(
        self,
        source_size: tuple[int, int],
        surface_size: tuple[int, int],
        *,
        title: str = DEFAULT_TITLE,
        finder: Callable[[], str | None] = _find_sdl2,
    ) -> None:
        self.source_size = (int(source_size[0]), int(source_size[1]))
        self.surface_size = (int(surface_size[0]), int(surface_size[1]))
        self.layout = plan_layout(self.source_size, self.surface_size)
        self._sdl = load_sdl2(finder)
        self._byte_count = self.source_size[0] * self.source_size[1] * 2
        self._pixels = ctypes.create_string_buffer(self._byte_count)
        self._event_buf = ctypes.create_string_buffer(_SDL_EVENT_SIZE)
        self._title = title
        self._window: int | None = None
        self._renderer: int | None = None
        self._texture: int | None = None
        self._dst_rect: SDL_Rect | None = None
        self._open()

    def _open(self) -> None:
        sdl = self._sdl
        sdl.init_video()
        sdl.set_scale_quality_nearest()
        self._window = sdl.create_window(self._title, *self.surface_size)
        self._renderer = sdl.create_renderer(self._window)
        self._texture = sdl.create_texture(
            self._renderer, SDL_PIXELFORMAT_RGB565, *self.source_size
        )
        self._dst_rect = SDL_Rect(
            self.layout.x, self.layout.y, self.layout.width, self.layout.height
        )

    def present(self, frame: object) -> None:
        """Upload one ``B5G6R5`` frame and blit it to the letterboxed rect."""
        data = _frame_bytes(frame, self._byte_count)
        ctypes.memmove(self._pixels, data, self._byte_count)
        self._sdl.update_texture(self._texture, self._pixels, self.source_size[0] * 2)
        self._sdl.render_clear(self._renderer)
        self._sdl.render_copy(self._renderer, self._texture, self._dst_rect)
        self._sdl.render_present(self._renderer)

    def poll_quit(self) -> bool:
        """True when the window was closed (``SDL_QUIT``) or Esc was pressed."""
        while self._sdl.poll_event(ctypes.byref(self._event_buf)) != 0:
            event_type, key_sym = _decode_event(self._event_buf.raw)
            if event_type == SDL_QUIT or (event_type == SDL_KEYDOWN and key_sym == SDLK_ESCAPE):
                return True
        return False

    def set_title(self, title: str) -> None:
        self._title = title
        if self._window:
            self._sdl.set_window_title(self._window, title)

    def close(self) -> None:
        sdl = self._sdl
        if self._texture is not None:
            sdl.destroy_texture(self._texture)
            self._texture = None
        if self._renderer is not None:
            sdl.destroy_renderer(self._renderer)
            self._renderer = None
        if self._window is not None:
            sdl.destroy_window(self._window)
            self._window = None
        sdl.quit()

    def __enter__(self) -> "Window":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_window(
    source_size: tuple[int, int],
    surface_size: tuple[int, int],
    *,
    frames: Iterator[object] | None = None,
    max_frames: int | None = DEFAULT_MAX_FRAMES,
    fps: float = 60.0,
    title: str = DEFAULT_TITLE,
    finder: Callable[[], str | None] = _find_sdl2,
) -> None:
    """Open a window and run the paced present loop until quit or exhaustion.

    ``frames`` is an iterable of ``B5G6R5`` buffers (bytes or ``.to_bytes()``
    objects); when omitted a synthetic animated pattern is shown.  The loop
    stops on a quit event (window close or Esc), when ``frames`` is exhausted,
    or after ``max_frames`` ticks — so it terminates even headless, where no
    input can arrive.  When SDL2 is missing it prints one line and exits 1.
    """
    try:
        window = Window(source_size, surface_size, title=title, finder=finder)
    except SDL2MissingError as exc:
        print(str(exc))
        raise SystemExit(1) from None

    frame_iter = iter(frames) if frames is not None else _synthetic_frames(source_size)
    interval = 1.0 / fps
    tick = 0
    try:
        while max_frames is None or tick < max_frames:
            tick_start = time.monotonic()
            try:
                frame = next(frame_iter)
            except StopIteration:
                break
            window.present(frame)
            if window.poll_quit():
                break
            _sleep_to(tick_start, interval)
            tick += 1
    finally:
        window.close()


if __name__ == "__main__":  # pragma: no cover - manual smoke path
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <source_w>x<source_h> <surface_w>x<surface_h>")
        raise SystemExit(2)
    src = tuple(int(v) for v in sys.argv[1].lower().split("x"))
    surf = tuple(int(v) for v in sys.argv[2].lower().split("x"))
    open_window(src, surf)
