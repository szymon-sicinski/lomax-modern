# Scripts

Helper scripts for contributors. Nothing here is shipped in the package.

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
