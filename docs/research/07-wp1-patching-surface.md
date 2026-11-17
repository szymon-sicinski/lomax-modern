# 7/WP-1 — Patching surface: import table, MFC 4.2 startup order, DLL-proxy feasibility

> **Provenance.** Work package **WP-1** of the LMX-7 roadmap, delivered as an
> attachment on kanban card `t_f46072b8` (2026-11-17) and committed here
> unchanged apart from the heading level and relative links. It is a read-only
> pass over the retail PC install: `objdump -p` and `file` against `LOMAX.EXE`,
> and nothing in the game folder was written.
>
> **No game bytes, no whole-file hashes.** Every figure below is a count, an
> offset, a header field or an imported function name. No payload bytes and no
> digest of a copyrighted file appear anywhere in this document.
>
> **Scope.** Decide how an open-source presenter reaches Lomax's finished frame
> without modifying `LOMAX.EXE`. Lomax+ facts are cited `[S#]` per
> [`sources.md`](sources.md); DirectDraw / MFC API ordering is public SDK
> knowledge and is marked as such.
>
> **Grades.** As the report left them: **V** measured in that session with the
> command quoted, **D** documented by a third party, **H** hypothesis with its
> test named.

## 1. Executable identity (measured)

```
file: PE32 executable for MS Windows 4.00 (GUI), Intel i386, 6 sections
Magic 010b (PE32)           Subsystem 0002 (Windows GUI)
ImageBase        0x00400000
AddressOfEntryPoint 0x0003AD40
MajorLinkerVersion 4  MinorLinkerVersion 20   (MSVC 4.x, matches MFC 4.2 [S2])
Export Directory  Entry 0 -> 0 (no exports)
Delay Import Dir  Entry 13 -> 0 (no delay-loaded imports)
```

- **Statically linked CRT and MFC.** The import table contains no `MSVCRT*.dll`,
  no `MSVCRT20.dll`, no `MFC42.dll`. This confirms `[S2]` "statically linked MSVC
  runtime" from the binary itself.
- **The executable exports nothing**, so the only way *in* from outside is an
  import it already has, or loading a DLL whose presence it triggers.

## 2. Import table (measured — full DLL list, 13 entries)

`objdump -p` (interpreted `.idata`) lists these DLLs, in this order:

```
ole32.dll      CoInitialize, CoCreateInstance, CoUninitialize
WINMM.dll      auxGetVolume, timeGetDevCaps, timeSetEvent, auxGetNumDevs,
               auxSetVolume, timeGetTime, mciSendStringA, auxGetDevCapsA,
               timeKillEvent, joyGetPosEx
DDRAW.dll      DirectDrawCreate          <-- the ONLY DirectDraw import
DSOUND.dll     DirectSoundCreate         <-- the ONLY DirectSound import
DINPUT.dll     DirectInputCreateA        <-- the ONLY DirectInput import
KERNEL32.dll   (file/heap/thread/registry-adjacent primitives; GetProcAddress,
               LoadLibraryA, VirtualAlloc, …)
USER32.dll     (window mgmt, dialogs, messages; SetWindowsHookExA, …)
GDI32.dll      (DIB/bitmap/DC blitting — see §3)
comdlg32.dll   GetFileTitleA             (single import)
WINSPOOL.DRV   ClosePrinter, DocumentPropertiesA, OpenPrinterA  (MFC print stub)
ADVAPI32.dll   RegOpenKeyExA, RegSetValueExA, RegQueryValueExA, RegCloseKey,
               RegCreateKeyExA           (config registry path [S1])
SHELL32.dll    (import descriptor present but no function entries decoded — empty
               thunk list in objdump's view)
COMCTL32.dll   CreatePropertySheetPageA, DestroyPropertySheetPage,
               PropertySheetA, ordinal 17 (InitCommonControls), ImageList_Destroy
```

Two measured facts fall straight out of this:

1. **The five DLLs documented in prior research are confirmed, and the real
   surface is richer.** `DDRAW.dll`, `DINPUT.dll`, `DSOUND.dll`, `WINMM.dll`,
   `COMCTL32.dll` `[S2]` are all present, plus `ole32.dll` (the COM init that
   precedes every `DirectXCreate` call), `GDI32.dll`, `USER32.dll`, `KERNEL32.dll`,
   `ADVAPI32.dll`, `comdlg32.dll`, `WINSPOOL.DRV`, `SHELL32.dll`.
2. **The COMCTL32 imports prove the main UI is an MFC property sheet** —
   `PropertySheetA` / `CreatePropertySheetPageA` / `DestroyPropertySheetPage` plus
   `InitCommonControls` by ordinal — which is the concrete object behind the MFC /
   CTL3D startup hazard in `[S2]`/`[S3]` (see §5).

## 3. DirectDraw surface-creation and present surface (the intercept targets)

This is the decisive observation for the whole card:

> **`DDRAW.dll` is imported for exactly one named function, `DirectDrawCreate`.**
> There is no `DirectDrawCreateEx`, no `DirectDrawEnumerateA`, nothing else. Every
> surface operation — mode set, surface creation, blit, flip, lock — therefore
> happens through the COM interface *returned by* `DirectDrawCreate`, not through
> the import table.

Because the entry point is `DirectDrawCreate` (not `DirectDrawCreateEx`), the game
obtains an `IDirectDraw` (v1) and then reaches DirectDraw 7 by `QueryInterface`
(`[S2]` "DirectDraw 7 for surfaces/present"). The full intercept surface is thus:

**Named import (the only hook point the PE loader can see):**
- `DDRAW.dll!DirectDrawCreate`

**Vtable methods a proxy must wrap** (public DirectDraw 7 SDK; not in the import
table — they are entries in the vtables of the interfaces the game receives):

| Interface | Methods that matter for surface creation / present |
|---|---|
| `IDirectDraw` | `QueryInterface` (return wrapped `IDirectDraw7/4/2`, `IDirectDrawSurface7`…), `SetCooperativeLevel`, `SetDisplayMode`, `CreateSurface`, `GetCaps`, `FlipToGDISurface` |
| `IDirectDraw7` | `CreateSurface`, `WaitForVerticalBlank` |
| `IDirectDrawSurface` (7) | `Blt`, `BltFast`, `Flip` (the **present** calls), `GetDC`/`ReleaseDC`, `Lock`/`Unlock`, `GetSurfaceDesc`, `IsLost`/`Restore` |

- **Present** is `Flip` (exclusive fullscreen) or `Blt`/`BltFast` to the primary
  (windowed / manual present). The game has both windowed and fullscreen paths
  (`[S1]` 8/16-bpp gate), so the proxy should watch all three.
- **Frame pixels** are readable at present by wrapping `Flip`/`Blt` (copy the
  source surface), or by wrapping `Lock`/`GetDC` on the surface the game renders
  into. No exe byte is touched to do this.
- **The GDI half of the renderer is visible in `GDI32.dll` imports:**
  `CreateDIBitmap`, `CreateBitmap`, `CreateCompatibleDC`, `SelectObject`,
  `BitBlt`, `StretchDIBits`, `SetStretchBltMode`, `GetSystemPaletteEntries`,
  `GetDeviceCaps`. `[S2]` says sprites are palettised surfaces blitted through GDI
  DCs; the measured presence of `CreateDIBitmap`+`StretchDIBits` (and *absence* of
  `GetDIBits`/`SetDIBitsToDevice`/`CreateDIBSection`) matches "assemble palettised
  DIBs into a DC". Note also what is *not* imported from GDI32: no
  `CreatePalette`/`SelectPalette`/`RealizePalette`, only `GetSystemPaletteEntries`
  — consistent with palette ownership living on the DirectDraw side
  (`IDirectDrawPalette`, vtable) rather than in GDI. If the finished frame is ever
  blitted via GDI, it still lands on a DirectDraw surface DC (`GetDC`) and is
  presented by DirectDraw — the proxy sees it either way.

## 4. DirectSound and WinMM imports (audio / timing / input)

These are not "present", but the card asks for the full list:

- `DSOUND.dll!DirectSoundCreate` — single import, same pattern as DDRAW; the whole
  DirectSound interface (mixer) is vtable. Not needed for presentation, but it
  means the proxy pattern generalises to audio later (`[S2]` DirectSound software
  mixer).
- `WINMM.dll`:
  - `mciSendStringA` — the MCI `cdaudio` path (`[S3]` CD check / CD-DA music).
  - `timeGetTime`, `timeGetDevCaps`, `timeSetEvent`, `timeKillEvent` — the
    multimedia timer behind the 60 Hz tick (`[S2]`).
  - `auxGetNumDevs`, `auxGetDevCapsA`, `auxGetVolume`, `auxSetVolume` — mixer
    volume.
  - `joyGetPosEx` — **legacy WINMM joystick polling, in addition to**
    `DINPUT.dll!DirectInputCreateA`. A measured extra beyond Q4: the PC build
    carries *both* a DirectInput path and a `joyGetPosEx` path.

## 5. MFC 4.2 startup order and the safe injection point

Startup order (public MFC 4.2 documentation, cross-checked against the measured
imports in §2):

1. **PE loader resolves the import table** and maps every imported DLL — this is
   where a dropped-in `ddraw.dll` proxy is loaded, *before any game code runs*.
2. **CRT startup** (`mainCRTStartup`/`WinMainCRTStartup`, statically linked) →
   `WinMain`.
3. **MFC `_tWinMain` → `AfxWinMain`** (statically linked):
   - `AfxWinInit` — MFC module/thread state; CTL3D registration.
   - `CWinApp::InitApplication`.
   - `CWinApp::InitInstance` — the game's override. This is where it reads its
     registry config (`ADVAPI32 Reg*`), creates the main window and the
     **property sheet** (`COMCTL32 PropertySheetA/CreatePropertySheetPageA`,
     `InitCommonControls` ordinal 17), with CTL3D auto-subclassing on this thread.
   - `CWinApp::Run` — the message loop (`USER32 GetMessage/TranslateMessage/
     DispatchMessage`); the game loop runs inside it via `WINMM timeSetEvent`.
4. **DirectDraw init** — `DDraw_InitSurfaces` / `Display_SetVideoMode` `[S2]` — the
   game's own main thread calls `DirectDrawCreate`. **This is the first moment a
   `ddraw.dll` proxy executes any of our code.**

**The hazard** (`[S3]`, confirmed by the measured COMCTL32 imports): the menu is a
property sheet whose CTL3D/common-control init must run on the game's own main
thread, after `AfxWinInit` has set up MFC module state. Lomax+ documents that it
"has to let the game's own thread reach the entry point before injecting" — i.e.
starting the process the wrong way round, or driving `InitInstance` from a foreign
thread, breaks the property sheet/CTL3D init.

**The safe injection point is therefore: the game's own main thread, after
`AfxWinInit`/CTL3D registration, at the first `DirectDrawCreate`.** A DLL proxy
satisfies this *by construction*: it is loaded at step 1 but stays inert in
`DllMain` (which runs under the loader lock), and all of its work happens inside
its `DirectDrawCreate` forward — which is, precisely, after the hazard. An
app-level loader must *engineer* that timing; the proxy gets it for free.

## 6. Mechanism matrix and recommendation

| Mechanism | Verdict | Why |
|---|---|---|
| **Dropped-in `ddraw.dll` proxy** | **Recommended** | Import-table injection with zero exe modification; one hook point
(`DirectDrawCreate`) to wrap; runs at the safe injection point automatically; clean-room buildable from public DirectDraw 7 SDK docs; identical mechanism under Wine (`WINEDLLOVERRIDES="ddraw=n,b"` or a file next to the exe) and on Windows (same file); we ship our own MIT code and no game byte. |
| App-level loader (in-memory patcher / frame grabber) | Loses | (a) In-memory patcher is what Lomax+ is — high complexity, pinned to the exe, exists to patch 199 width sites we do not need for L1, and it must hit the §5 hazard timing by hand `[S3]`. (b) A frame *grabber* (GDI `BitBlt` from the window DC / DXGI desktop duplication) sees only what is already on screen: it cannot change surface creation, cannot fix the 8/16-bpp gate, cannot position the window borderless, double-blits, and grabs the composited desktop. A fallback only if the proxy were impossible — it is not. |
| Wine registry override (`ddraw=native,builtin`) | Loses as a standalone answer | A `WINEDLLOVERRIDES` entry only *selects* which `ddraw` implementation loads; it hooks nothing and presents nothing by itself. It is the **install path** for the proxy under Wine, not a competing mechanism. |
| App-compat shim (`.sdb` / ACT) | Loses | Windows-only, opaque binary SDB format, no Wine/Linux equivalent; its DirectDraw shims (e.g. force-emulation) merely redirect to a *wrapper DLL* — you re-derive the proxy with an extra opaque layer. At best a Windows distribution nicety. |

**Recommendation.** Build the presenter as a clean-room **`ddraw.dll` proxy** that
exports `DirectDrawCreate`, forwards it to the real `ddraw.dll`, wraps the returned
`IDirectDraw` (and, via its `QueryInterface`, the `IDirectDraw7` and
`IDirectDrawSurface7` it hands back), and observes/presents at `Flip`/`Blt`. Under
Wine it is installed by dropping the DLL beside `LOMAX.EXE` (or the
`ddraw=n,b` override); on Windows by the same drop-in. This directly answers the
card's verify question:

> **Can a `ddraw.dll` proxy observe the finished frame without patching the exe?
> Yes.** The exe imports `DDRAW.dll!DirectDrawCreate` (and only that). Placing a
> proxy `ddraw.dll` on the search path makes the PE loader bind that import to our
> code; we forward to the real implementation and wrap the returned surface vtables,
> so the present call (`Flip`/`Blt`) and the surface pixels (`Lock`/`GetDC`) are
> observable with the executable byte-for-byte untouched. No relocations, no entry
> point changes, no hex patch.

## 7. What this leaves for WP-2 / WP-4 (runtime-only, `blocked` here)

- Which call is the *final* present in each mode — `Flip` vs `Blt` vs a GDI
  `StretchDIBits` — is a runtime question, not an import-table question. The proxy
  should defensively log/intercept all three (this is WP-2's probe).
- Whether Wine's built-in DirectDraw already presents 16-bit surfaces well enough
  that only a filter pass is needed is WP-4's falsifier, not decidable from the
  binary.
- The 8/16-bpp desktop gate and the 320x240 exclusive-mode absence (`[S1]`) sit
  *inside* the game's calls, so they fire before our proxy's `DirectDrawCreate`
  returns; the proxy can pre-empt them (e.g. report/adopt a 32-bpp-compatible
  surface in `CreateSurface`/`SetDisplayMode`) — the exact sites are WP-2.
