# Scripts

Helper scripts for contributors. Nothing here is shipped in the package.

- `new_game_folder.sh <repository-name> [variant ...]` — creates a local-only
  game-data slot next to the repository (`$HOME/projects/game-files/<repo>/`),
  outside every git working tree, and refuses to run if the target would sit
  inside one. See [`docs/development.md`](../docs/development.md#game-files-local-only).
- `measure_worlds.py <game_dir> [--json PATH] [--quiet]` — the Phase 0 probe:
  chunk sequence and counts, plane-width histogram per section, audio formats,
  `GAME.TXT` and `DEMOS` structure. Thin wrapper over
  `lomax_modern.measure`; read-only and prints no asset bytes.

Planned:

- `check_no_game_data.sh` — fail if a staged file looks like game data
  (`LOMAX.EXE`, `*.WLD`, `*.WAV` over a size threshold, disc images), to catch
  accidents before a commit.
- `measure_worlds.py` — the Phase 0 measurement harness (map-width histogram,
  palette usage, asset counts) once the `WLD` layout is confirmed (LMX-1/LMX-2).

Until then, the CLI covers the workflow:

```bash
lomax-modern doctor /path/to/Lomax
lomax-modern wldscan /path/to/Lomax/WORLDS/MAIN.WLD
```
