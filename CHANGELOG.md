# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Research report: platform assessment (Win32/MFC/DirectDraw 7, not DOS),
  three-layer resolution analysis, prior-art and licence review, ranked
  improvement backlog, open questions, cited source list.
- `lomax-modern` CLI with two read-only commands:
  - `doctor <game_dir>` — install inventory (presence, counts, sizes, SHA-256 of
    the executable, world-file listing). Prints no file contents.
  - `wldscan <file>` — `.WLD` chunk scanner that ranks header hypotheses
    (tag/size order, endianness, size semantics) and reports tag names and
    offsets without decoding payloads.
- Synthetic chunk-container fixtures and 16 unit tests, including negative cases
  (unaligned sizes, truncation, garbage, unknown tags).
- Measurement probe: `lomax-modern measure` / `scripts/measure_worlds.py` reports
  the chunk sequence and counts per world file, the plane-width histogram per
  section (the number that decides the widescreen ceiling), the HEAD endianness
  vote, RIFF/WAVE formats in `SFX`/`AMBIENT`/`JINGLES`, `GAME.TXT` structure and
  `DEMOS` framing — read-only, sizes and header fields only, with the documented
  HEAD layout labelled as a hypothesis until real files confirm it.
- Opt-in integration tests behind `LOMAX_GAME_DIR`.
- Local-only game-data layout: `scripts/new_game_folder.sh` creates one slot per
  repository outside every git working tree, and `.gitignore` covers
  `game-files/`, `gamedata/`, `GAMES/` as a second line of defence.
- CI workflow: Python 3.10–3.13, byte-compile, unit tests, CLI smoke test.
- Project scaffolding: `AGENTS.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
  `docs/development.md`, `docs/file-formats.md`, `.gitignore` covering game data.

### Notes

- No format layout has been verified against a real game file yet; every
  documented chunk claim is graded H/D in `docs/file-formats.md`.
- No engine work, no loader, no patcher in this release.

## [0.1.0] - 2026-11-16

Initial research-phase scaffold.
