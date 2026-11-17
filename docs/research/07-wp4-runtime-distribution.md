# 7/WP-4 — Runtime & distribution: Wine/Proton vs native port vs shim

> **Provenance.** Work package **WP-4** of the LMX-7 roadmap, delivered as an
> attachment on kanban card `t_1025ab57` (2026-11-17, author *scout*) and
> committed here unchanged apart from the heading level and relative links. It is
> a read-only pass: nothing was committed from that session, and no file in the
> game slot was written.
>
> **No game bytes, no whole-file hashes.** What is quoted from the binary is
> disassembly at named addresses, the import-table entries those addresses
> resolve to, and one dialog string. No payload bytes and no digest of a
> copyrighted file appear anywhere in this document.
>
> **Scope.** Answers **LMX-3**, feeds **WP-6** (synthesis).
>
> **Grades** used for every claim: **V** = verified in that session (command
> output quoted) · **D** = documented by an outside source · **H** = hypothesis,
> test listed.

---

## 1. What this environment could and could not do

| Fact | Evidence |
|---|---|
| Sandbox is a Fedora 44 **container**, uid 1000, `sudo` refuses (`no new privileges`), no display | `id` → `uid=1000(dev)`; `sudo -n true` → `The "no new privileges" flag is set`; `DISPLAY=unset`, no `/tmp/.X11-unix` |
| No Wine binary present, and it cannot be installed here | `wine --version` → `wine: command not found`; `sudo` unusable |
| Fedora 44 repos **do** carry what the recipe needs | `dnf -q list --available wine wine-core` → `wine.x86_64 11.21-1.fc44`, `wine-core.x86_64 11.21-1.fc44`; `xorg-x11-server-Xephyr.x86_64 21.1.26-1.fc44` |

**Consequence:** no cell of the matrix below was executed against the retail
binary. Every Wine behaviour is derived from (a) the Wine source at `master`
(= the 11.x line Fedora ships), (b) Wine's own release notes, (c) one archived
AppDB field report on Wine 1.7.0, and (d) the game binary itself, which I did
re-disassemble. Cells that depend on the un-runnable combination are marked
**H** with the exact probe that settles them (§7).

I did **not** attempt to start the game: there is no Wine, no X server, no
32-bit runtime in this container, and the card forbids installing packages in
my role. That is the explicit reason, not an omission.

---

## 2. Blocker 1 re-verified from the binary — and it decides the matrix

Prior research ([`01-platform-assessment.md`](01-platform-assessment.md) §1.3)
places the colour gate at `0x40799c`. This session's disassembly shows *exactly*
what it reads, which is what determines whether any wrapper can satisfy it:

```
0040796a: push ebx                       ; ebx = 0  (NULL hwnd)
0040796b: call DWORD PTR ds:0x5a8a10     ; -> 005a8a10 = USER32.GetDC   (screen DC)
00407971: mov  esi,eax
00407973: push 0xc                       ; 12 = BITSPIXEL
00407975: push esi
00407976: mov  edi,DWORD PTR ds:0x5a8658 ; -> 005a8658 = GDI32.GetDeviceCaps
0040797c: call edi
0040797e: mov  ebp,eax
00407980: push 0xe                       ; 14 = PLANES
00407982: push esi
00407983: call edi
00407985: imul ebp,eax                   ; ebp = BITSPIXEL * PLANES
00407989: mov  DWORD PTR ds:0x461ce8,ebp
0040798f: push ebx
00407990: call DWORD PTR ds:0x5a89a0     ; -> 005a89a0 = USER32.ReleaseDC
0040799c: cmp  ebp,0x8                   ; == 8  -> continue
0040799f: je   0x4079bf
004079a1: cmp  ebp,0x10                  ; == 16 -> continue
004079a4: je   0x4079bf
004079a6: push ebx / push ebx / push 0x462be0 / call 0x45503e   ; fatal dialog
```

IAT confirmed with a PE import walk (`/tmp/pe_iat.py`):

```
005a8a10  USER32.dll     GetDC
005a8658  GDI32.dll      GetDeviceCaps
005a89a0  USER32.dll     ReleaseDC
```

and the dialog string in the binary is
`Lomax will only run on 8 and 16 bit deep desktops.` **V**

**This is a GDI query on the screen DC, taken before any DirectDraw mode set.**
Three consequences that shape everything else:

1. A DirectDraw-only wrapper (**dgVoodoo 2**) cannot satisfy it. It replaces
   `ddraw.dll`/`d3d*.dll`; it does not own `GetDeviceCaps` on the display DC
   `[S12]`. Predicted to still fire — **H** (probe P1).
2. A GDI-level hooker (**DxWnd**) can, and on Windows plainly does: VOGONS
   reports the game "seems to run fine in DxWnd" `[S4]`, with DxWnd's own
   release notes documenting display-mode neutralisation and ddraw surface
   emulation `[S13]`. Under Wine this is untested — **H**.
3. The honest, non-deceiving fix is to give the Wine process a **display that
   really is 16 bpp**. Wine's X11 driver explicitly supports 8/16/24/32-bpp
   screens (`dlls/winex11.drv/display.c:42-45`, `depths_24[] = {8,16,24}`,
   `depths_32[] = {8,16,32}`) **V**, and that depth is what `screen_bpp` /
   the reported `DEVMODEW` carries (`nores_get_modes`, same file, lines 93 and
   125) **V**.

---

## 3. Blocker 2 (missing 320x240 mode) — what Wine actually enumerates

* Wine's X11 backend default handler offers **exactly one mode**: the host
  primary rectangle at `screen_bpp` (`nores_get_modes`,
  `dlls/winex11.drv/display.c:76-101`) **V** — so a 320x240 mode is not in the
  list, and a mode-change request is *ignored but reported successful* by that
  handler (`nores_set_current_mode`, line 132-136: `WARN("NoRes settings
  handler, ignoring mode change request")` → `DISP_CHANGE_SUCCESSFUL`) **V**.
* Wine ≥ 10 added an opt-in emulated modesetting path: `EmulateModeset=Y`
  under `HKCU\Software\Wine\X11 Driver` `[S10]`
  (`dlls/win32u/sysparams.c:6093`, UI in `dlls/desk.cpl/main.c:245-257`,
  `RegSetValueExW(..., L"EmulateModeset", ..., L"Y")`) **V**; with it,
  `ChangeDisplaySettings` always succeeds and the requested mode is stored
  (`sysparams.c:4508`: `if (is_virtual_desktop() || emulate_modeset) ret =
  DISP_CHANGE_SUCCESSFUL;`) **V**.
* The virtual mode list that this exposes is built from
  `default_sizes[] = {640x480, 800x600, 1024x768, 1152x864, 1280x960,
  1600x1200, 960x540, 1280x720, 1600x900, ...}` at depths
  `{8, 16, current}` (`sysparams.c:2085-2100`, `2148-2206`) **V** — **320x240
  is not in it**. So even the emulated path does not *advertise* 320x240.
* ddraw passes 8/16-bit mode requests straight to wined3d and maps
  8 → `P8_UINT`, 16 → `B5G6R5` (`dlls/ddraw/ddraw.c:1121-1139`) **V**, and
  enumerates modes filtered to 32/16/8-bit formats
  (`ddraw7_EnumDisplayModes`, `ddraw.c:2466-2500`) **V**. So the API layer is
  willing; the question is only whether the requested geometry survives.

Net: under Wine the game does not get a real 320x240 mode; it gets either a
window (stock Wine) or an emulated mode that is padded/scaled to the physical
display (Wine ≥10 with `EmulateModeset`) `[S10]`. That is *presentation*, not a
framebuffer change — see [`02-resolution.md`](02-resolution.md) §2.6 for why that
distinction matters for LMX-4.

---

## 4. Compatibility matrix

Rows are what the user launches; columns are the host stack. Each cell reads
`B1 / B2 / B3 / B4`, where **✗ fires**, **✓ cleared**, **– not applicable**,
and `?` marks the part that is unverified (**H**).

### 4.1 Wine 11.x on a normal 32-bpp X11/Wayland desktop (`DISPLAY` on XWayland)

| Row | B1 colour gate | B2 320x240 mode | B3 CD check | B4 MFC/start order |
|---|---|---|---|---|
| stock `LOMAX.EXE` | ✗ fires — screen DC reports 24/32 bpp **V** | ✗ only the host mode is enumerated **V** | ✗ needs a disc drive | – the game's own thread starts normally, so the loader-order problem does not exist |
| + DxWnd (Windows binary, closed) | ? DxWnd hooks GDI/display **H** | ✓ its virtual desktop + surface emulation **D** `[S13]` | ✗ | – |
| + dgVoodoo 2 (Windows DLLs, closed) | ✗ predicted still fires (GDI, not ddraw) **H** | ✓ emulates ddraw modes and scales to its window **D** `[S12]` | ✗ | – |
| + Lomax+ (Windows loader, no licence) | ✓ "simulate 16bpp colour space" **D** `[S1]` `[S5]` | ✓ **D** `[S1]` | ✓ (loader skips it — we may not) | the loader *is* the reason this blocker exists **D** `[S3]` |

### 4.2 Same Wine, but the game's X display is really 16 bpp (`Xephyr :2 -screen 640x480x16`)

| Row | B1 | B2 | B3 | B4 |
|---|---|---|---|---|
| stock `LOMAX.EXE` | ✓ `screen_bpp` = 16, `BITSPIXEL*PLANES` = 16 **V**(mechanism) + **D** `[S8]` | ? Wine fakes/ignores the 320x240 change; the 2013 Wine 1.7 run did reach gameplay at 16 bpp **D** `[S8]` | ✗ without a disc; **✓ if the user's own disc or a CDEmu CD-DA device is present** (MCI `cdaudio` path is in the binary: `open cdaudio`, `set cdaudio time format tmsf`, `status cdaudio length track %d` **V**) | – |
| + DxWnd | ✓ (already 16 bpp) | ✓ | ✗ | – |
| + dgVoodoo 2 | ✓ (already 16 bpp) | ✓ | ✗ | – |
| + Lomax+ | ✓ | ✓ | ✓ (not shippable by us) | – |

Archived AppDB report (Wine **1.7.0**, Arch x86_64, 2013-08-03, rating Bronze)
`[S8]`: "Launching the game from the CD / Playing the game / In-game audio and
CD audio music" worked; the workaround was
`xinit /usr/bin/xterm -- :1 -ac -depth 16`; graphical bugs reported were
"sprites moving platforms are invisible, some sprites seems to be randomly
zoomed at maximum during one frame". This is the **only** public evidence that
the stock binary reaches gameplay under Wine at all, and it is 13 years old —
hence the `?` in row 2.

### 4.3 Virtual desktop only, DXVK only

| Stack | Effect on B1 | B2 | B3 |
|---|---|---|---|
| Lutris `wine: Desktop: true` / `wine explorer /desktop=` (no depth change) | ✗ — a virtual desktop is a window on the same X screen; reported depth stays 24/32 **V**(source) | ✗ (mode list unchanged) | ✗ |
| `EmulateModeset=Y`, no nested X | ? B1 **may** flip if the game sets a mode before querying caps — but the gate at `0x40799c` runs on the screen DC *before* any ddraw mode set, so ✗ is the expected reading **H** (probe P2) | partial: mode changes succeed but 320x240 is not in the advertised list **V** | ✗ |
| DXVK (`WINEDLLOVERRIDES` d3d9/11) | ✗ none — DXVK implements **Direct3D 8/9/10/11 only**, it does not touch ddraw or GDI **V** (`dxvk` README line 3) | ✗ | ✗ |

DXVK becomes relevant only **behind** dgVoodoo 2 (dgVoodoo presents through
D3D11/12 `[S12]`, so DXVK can carry it on Vulkan). dgVoodoo 2 under Wine also
needs explicit DLL overrides and a version known to work:
`WINEDLLOVERRIDES="ddraw=n,b"`, "versions below 84 should work" `[S11]`, with
2.79.3 and 2.81.3 mirrored as "the latest releases that are compatible with
Proton/Wine" `[S11]`.

### 4.4 Survivors, in one line each

* **B1 (colour gate)** survives on every stock-desktop stack. Cleared only by a
  genuinely 16-bpp display, a GDI-level hook (DxWnd), or Lomax+'s patch.
  dgVoodoo 2 and DXVK cannot clear it.
* **B2 (320x240)** survives stock Wine; cleared by dgVoodoo 2/DxWnd surface
  emulation or by Wine ≥10 `EmulateModeset` (padded/scaled, not native).
* **B3 (CD check)** survives everywhere except Lomax+ (D). It is **not** a
  Wine problem: it is a disc problem. Two licence-clean answers exist (real
  disc; the user's own image presented as a CD-DA-capable device) and we ship
  no third one.
* **B4 (MFC start order)** is an artefact of injection-based loaders, not of
  the game. Stock-under-Wine never meets it.

---

## 5. First-run recipe — Fedora 44 / Nobara 44 (verified package set)

Package availability verified in this session (§1). Nothing here redistributes
game data or bypasses the CD check.

```bash
# 1. Stack (wine 11.21 from Fedora, no external repo needed)
sudo dnf install wine wine-core xorg-x11-server-Xephyr

# 2. A 16-bpp X display. This is what clears B1; a virtual desktop is not.
Xephyr :2 -screen 640x480x16 -ac -resizeable &
export DISPLAY=:2

# 3. One prefix, created once (Wine 11: one default win64 prefix also runs
#    32-bit PE; WINEARCH=win32 is deprecated since 11.0)
export WINEPREFIX="$HOME/.local/share/lomax-wine"
wineboot -u

# 4. The CD check needs the user's own disc. Either insert it, or present the
#    user's own image as a CD-DA-capable device (CDEmu ships in RPM Fusion on
#    Fedora — verify before promising it):
#      sudo dnf install cdemu-daemon cdemu-client
#      cdemu load 0 /path/to/your/Lomax.cue
#    A loop-mounted ISO is not equivalent: it exposes no CD-DA tracks, and the
#    game opens MCI cdaudio for its music (strings: "open cdaudio",
#    "play cdaudio from %d to %d notify", "status cdaudio length track %d").

# 5. Play from the installed copy (no writing into the game folder)
LOMAX_GAME_DIR="$HOME/games/lomax"
cd "$LOMAX_GAME_DIR" && wine LOMAX.EXE

# 6. Verify audio before blaming the port: SFX are ordinary WAVs on disk
#    (SFX/AMBIENT/JINGLES, 82 RIFF/WAVE files per 05-open-questions Q7);
#    music is CD-DA through MCI and will be silent without step 4.
```

What this recipe is **not**: it gives no integer scaling, no widescreen and no
borderless — Xephyr's 640x480 window is scaled by the compositor, blurring a
320x240 image. Widescreen/CD-less music/16-bpp simulation are *already solved*
by Lomax+ — on Windows, unlicensed `[S5]`. We are not re-inventing them; we
are looking for a licensable path to them.

Unverified in this recipe (each with its probe): the 16-bpp Xephyr under a
modern Mesa/Vulkan driver (16-bpp visuals are increasingly refused by GPU
drivers — **H**), the Wine 11 behaviour of the 320x240 change (probe P1/P2),
and CDEmu-backed CD-DA under Wine (probe P3).

---

## 6. Packaging options for a shim (loads the user's own files)

Nothing in this project may contain game bytes; every option below is a
*launcher* that takes the user's install directory.

| Option | Carries | Verdict |
|---|---|---|
| **Lutris YAML** (recommended) | the whole runtime: `wine: version/overrides/Desktop`, `system: env:`, a `$GAMEDIR/run-lomax.sh` that starts Xephyr and exports `DISPLAY` `[S16]` | best effort/benefit; the runner already exists, users install it from Lutris's catalogue, and the YAML can declare `wine: overrides: {ddraw.dll: n}` for the dgVoodoo variant |
| **AppImage** | a launcher + `run-lomax.sh` + the checks; **not** Wine, **not** dgVoodoo (closed, no redistribution), **not** the game | good for "download and run"; must fail loudly with "install wine ≥10" instead of bundling a 300 MB prefix-less Wine; verify `--appimage-extract-and-run` works where FUSE is absent |
| **Flatpak** | `org.winehq.Wine` exists on Flathub as an *application*, not as a runtime/base for third-party launchers | not for v1: a nested 16-bpp X server plus a host Wine inside the sandbox needs `--socket=x11` and `flatpak-spawn --host`, which is more friction than the problem is worth |
| **Steam/Proton** | nothing of ours | irrelevant: the title has no Steam app to attach a compatibility profile to, and the retail EXE needs the CD |

Recommended split: **Lutris YAML first** (it is a file, reviewable in the repo,
no binaries), **AppImage second** (a single-file launcher for people who do not
use Lutris), Flatpak deferred.

---

## 7. CI: what can be built and smoke-tested headless

**Can** (no game data needed, all our own code):

1. Build the shim: `python -m pip install -e .` + `python -m compileall -q src`
   + `python -m pytest tests -m "not realgame" -q` — the existing
   `.github/workflows/tests.yml` already does exactly this on 4 Pythons.
2. Lint the packaging artefacts: YAML parse of the Lutris installer, shellcheck
   of `run-lomax.sh`, `appimagetool` build of the launcher.
3. **Prove the four blocker mechanics without the game.** A ~60-line Win32
   probe compiled with `i686-w64-mingw32-gcc` and run under `xvfb-run` at two
   depths answers B1/B2 with numbers instead of prose:

```c
/* tools/ddrawprobe.c — MIT, ours. Prints what the game's gate would read. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <ddraw.h>
#include <stdio.h>

static BOOL WINAPI count320(LPDDSURFACEDESC2 d, LPVOID ctx)
{
    if (d->dwWidth == 320 && d->dwHeight == 240) (*(int *)ctx)++;
    return DDENUMRET_OK;
}

int main(void)
{
    IDirectDraw7 *dd = NULL;
    HDC dc;
    int modes320 = 0;

    dc = GetDC(NULL);
    printf("devicecaps bits=%d planes=%d product=%d\n",
           GetDeviceCaps(dc, BITSPIXEL), GetDeviceCaps(dc, PLANES),
           GetDeviceCaps(dc, BITSPIXEL) * GetDeviceCaps(dc, PLANES));
    ReleaseDC(NULL, dc);

    if (FAILED(DirectDrawCreateEx(NULL, (void **)&dd, &IID_IDirectDraw7, NULL))) {
        puts("DirectDrawCreateEx failed");
        return 1;
    }
    if (SUCCEEDED(IDirectDraw7_EnumDisplayModes(dd, 0, NULL, &modes320, count320)))
        printf("modes_320x240=%d\n", modes320);
    printf("SetDisplayMode_320x240x16=%s\n",
           SUCCEEDED(IDirectDraw7_SetDisplayMode(dd, 320, 240, 16, 0, 0)) ? "OK" : "FAILED");
    IDirectDraw7_Release(dd);
    return 0;
}
```

```
# CI job (ubuntu-latest), headless, no game data:
sudo dpkg --add-architecture i386 && sudo apt-get update
sudo apt-get install -y wine wine32:i386 xvfb gcc-mingw-w64-i686
i686-w64-mingw32-gcc -o ddrawprobe.exe tools/ddrawprobe.c -lddraw -ldxguid
for d in 24 16; do
  xvfb-run -s "-screen 0 640x480x$d" wine ddrawprobe.exe | tee "probe-$d.txt"
done
diff probe-24.txt probe-16.txt   # must differ: product 24 vs 16
```

(Compiled and run in CI only — not built or executed in this container: no
`i686-w64-mingw32-gcc`, no Wine, no X.)

**Cannot**: run the retail binary. CI has no game data (and may not: no game
bytes anywhere), the binary needs the disc, and a headless runner cannot judge
"no graphical corruption". So the acceptance for any presentation work stays a
human run on a real GPU — the probe is the *only* honest automated gate.

**Probes still owed (P1–P3)**, all two-line commands for whoever has Wine:
* **P1** `DISPLAY=:2 wine ddrawprobe.exe` at depth 16 vs 24 → B1 mechanism.
* **P2** same with `EmulateModeset=Y` at depth 32 → does B1 stay ✗, does B2
  improve.
* **P3** `cdemu load 0 your.cue` then `wine LOMAX.EXE` → B3 clears, music plays.

---

## 8. Answer: Wine/Proton vs native port vs shim

| Path | Delivers for a disc-less modern Linux user? | Licence | Verdict |
|---|---|---|---|
| Wine + stock EXE | **no** — B1 and B3 survive; B2 has no native answer; no scaling/widescreen | fine (user's own files) | supported *documented* path for disc owners (§5), not a product |
| Wine + DxWnd | maybe B1+B2 (untested on Wine, closed source, Windows-only tool) | facts-only; cannot bundle | research only |
| Wine + dgVoodoo 2 | B2 yes, B1 **no** (GDI gate) | closed, cannot bundle | recommended *optional* companion for B2/upscaling once P1 confirms B1 is untouched |
| Wine + Lomax+ | yes on Windows, all four — but Windows-only, unlicensed, and it is the competition | **no licence** | cite facts; do not depend |
| **Our own engine + presenter over the data layer** | **yes** — never calls the CD check because it never runs the retail EXE | MIT code, no game bytes | **the deliverable** |

**Recommended next card (M2 presenter target host):** our own presenter over
the MIT data layer, targeting **Linux/x86-64 with a 32-bpp display and an
unchanged framebuffer of 320x240 presented at integer scale**, with Wine +
Xephyr-at-depth-16 kept as the *conformance oracle* (same data, compare
frames) and as the documented fallback for disc owners. Rationale: every
Wine-only route for a disc-less user is blocked by B3 or by B1, and the
one stack that clears all four (Lomax+) is Windows-only and unlicensed.

---

## 9. Sources used (recorded in [`sources.md`](sources.md) as `[S8]`–`[S16]`)

Existing tags reused: `[S1]` PCGamingWiki Lomax page (API table, 8/16-bpp
requirement, Lomax+ feature list) · `[S3]` `Hipnosis183/Lomax` loader notes
(CD check, MFC start order, install manifest) · `[S4]` VOGONS thread (hex
patch, DxWnd runs the game; the retail hash on that page is deliberately not
reproduced here) · `[S5]` Lomax+ readme (no licence).

New tags proposed:

| Tag | Source | Claim taken |
|---|---|---|
| `[S8]` | WineHQ AppDB, *Lomax 1*, version test by LunaVorax, Wine 1.7.0, Arch x86_64, 2013-08-03 — <https://appdb.winehq.org/objectManager.php?sClass=version&iId=3884> (archived: `web.archive.org/web/20240221150621/…`) | stock game launches and plays from CD under a **depth-16 X server** (`xinit … -- :1 -ac -depth 16`); CD audio music works; graphical glitches (invisible moving platforms, one-frame sprite zoom); otherwise refuses to launch |
| `[S9]` | Wine source, `master` (mirror `github.com/wine-mirror/wine`) | `dlls/ddraw/ddraw.c:1121-1139` (8/16-bpp SetDisplayMode → P8/B5G6R5), `:2466-2500` (EnumDisplayModes filtered to 32/16/8); `dlls/winex11.drv/display.c:42-45` (supported depths 8/16/24/32), `:76-101` (one mode = host size at `screen_bpp`), `:132-136` (mode change ignored, returns success); `dlls/win32u/sysparams.c:2148-2206` (virtual mode list), `:4508` (`is_virtual_desktop() || emulate_modeset` → `DISP_CHANGE_SUCCESSFUL`), `:6093` (`EmulateModeset` key); `dlls/desk.cpl/main.c:245-257` (writes `HKCU\Software\Wine\X11 Driver\EmulateModeset`) |
| `[S10]` | WineHQ news, *Wine 10.0 Released* (2025-01-21) & *Wine 11.0 Released* (2026-01-13) | opt-in emulated modesetting (pad/scale to physical display, `desk.cpl` control); Wine 11 is the current stable line, one 64-bit prefix runs 32-bit PE |
| `[S11]` | PCGamingWiki, *DgVoodoo 2* and the community file *dgVoodoo2 v2.79.3 & v2.81.3 (Wine/Proton compatible)* | under Linux/Wine dgVoodoo 2 needs `WINEDLLOVERRIDES="ddraw=n,b"`; "versions below 84 should work"; 2.79.3/2.81.3 are the last Wine/Proton-compatible releases |
| `[S12]` | dgVoodoo 2 official *About* (`dege.freeweb.hu/dgVoodoo2`) | implements DirectX 1–7 (all DirectDraw/Direct3D ≤ 7), Glide, D3D8.1, D3D9 on Direct3D 11/12 output devices; Windows 7+ |
| `[S13]` | DxWnd release notes (`github.com/DxWnd/DxWnd.reloaded`, `build/readme-relnotes.txt`) | hooks DirectDraw, emulates primary/backbuffer on a virtual desktop, 8-bpp palettized handling, `ChangeDisplaySettings`/registry modes neutralised |
| `[S14]` | DXVK README | Vulkan translation for **Direct3D 8/9/10/11** only — no DirectDraw, no GDI |
| `[S15]` | `Xvfb(1)`, Debian manpages | `-screen screennum WxHxD` sets depth; "the fb code for any depth can be exercised … without the need for real hardware" |
| `[S16]` | Lutris docs, `docs/installers.rst` | installer YAML keys used in §6: `wine: version`, `wine: overrides`, `wine: Desktop`, `system: env`, `game: exe/prefix/working_dir` |

Local measurements in this document (no external source): the disassembly at
`0x40796a–0x4079a4`, the IAT walk, the dialog string, the MCI `cdaudio`
command strings, the import-table DLL list, the `dnf list` package versions.
No game bytes and no binary digest of a game file are included.

---

## 10. New open questions for WP-6 ([`05-open-questions.md`](05-open-questions.md))

| # | Question | How to resolve |
|---|---|---|
| Q15 | Does Wine 11.x still pass B1 with a 16-bpp X server, or has something in 12 years broken it? | probe P1 on a real host |
| Q16 | Do the 2013 glitches (invisible platforms, one-frame sprite zoom) persist on Wine 11, and does dgVoodoo 2 remove them? | play test |
| Q17 | Does a CDEmu-backed CD-DA device satisfy both the disc check and `open cdaudio`? | probe P3 |
| Q18 | Does `EmulateModeset=Y` change what B1 sees (the gate runs before any mode set)? | probe P2 |
| Q19 | Are 16-bpp X screens still usable under Mesa/XWayland on modern GPUs, or is Xvfb+VNC the only reliable depth-16 vehicle? | run Xephyr at depth 16 on the target GPU; fall back to Xvfb |
