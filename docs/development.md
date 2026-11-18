# Development

## Requirements

- Python 3.10+ (CI runs 3.10–3.13)
- No runtime dependencies. `pytest` is the only dev requirement.
- A C99 compiler (`cc`) is needed only to build `native/` (CI-only; the Python
  package installs and tests without one).
- Optional: a copy of your own Lomax installation for the integration tests.

## Setup

```bash
git clone https://github.com/szymon-sicinski/lomax-modern
cd lomax-modern
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Everyday commands

```bash
python -m pytest tests -m "not realgame" -q     # unit tests (no game files)
python -m pytest tests -q                       # same, realgame skipped
LOMAX_GAME_DIR=/path/to/Lomax python -m pytest tests -m realgame -s
python -m compileall -q src tests
lomax-modern --version
lomax-modern doctor /path/to/Lomax
lomax-modern wldscan /path/to/Lomax/WORLDS/MAIN.WLD
LOMAX_GAME_DIR=/path/to/Lomax python -m lomax_modern wld roundtrip --check
lomax-modern probe-anim-nmy /path/to/Lomax        # structural probe, report only
lomax-modern anim-nmy /path/to/Lomax              # decode the recovered framings
make -C native test                            # build + run the C renderer smoke
```

## Testing rules

1. **Synthetic fixtures only** in unit tests. `tests/fixtures/synth.py` builds
   chunk containers from scratch; no game bytes ever enter the repository.
2. **Every parser needs a round-trip test** (bytes in == bytes out) before it is
   used for writing anything.
3. **Real-install tests are opt-in** (`-m realgame` + `LOMAX_GAME_DIR`) and must
   skip cleanly when the variable is unset. CI never has game files.
4. **Negative tests matter more than positive ones** for format work: unaligned
   sizes, truncated files, unknown tags, garbage input. All four are covered in
   `tests/unit/test_wldscan.py`.
5. A bug fix comes with a test that fails before the fix.

## Adding a format parser

Use this order, and stop at the first step that fails:

1. Add a synthetic fixture that encodes the documented layout.
2. Extend the scanner so the fixture is detected with `confirmed-chain`.
3. Verify the hypothesis against a real file with `wldscan`; record what you
   saw in `docs/file-formats.md` (change **H** → **V** with the evidence).
4. Only then decode payloads, behind a function that validates lengths instead
   of trusting them.
5. Add a byte-exact rebuild test.

## Game files (local only)

Game data must never enter this repository, so it lives in a sibling tree that
is not a git repository at all:

```
$HOME/projects/
├── lomax-modern/            the repository (this)
└── game-files/              not a repo, not publishable
    └── lomax-modern/        one folder per repository
        ├── pc-retail/       LOMAX.EXE, WORLDS/, SFX/, DEMOS/, ...
        └── pc-disc/         optional .bin/.cue image
```

Create a slot for a new project (never inside a checkout):

```bash
scripts/new_game_folder.sh lomax-modern pc-retail
```

Point the tools at the variant folder, not at the slot root:

```bash
export LOMAX_GAME_DIR="$HOME/projects/game-files/lomax-modern/pc-retail"
lomax-modern doctor "$LOMAX_GAME_DIR"
python -m pytest tests -m realgame -s
```

Verify the guarantee before adding data:

```bash
git -C "$HOME/projects" rev-parse --show-toplevel   # must fail: not a repo
```

Three independent layers keep it unpublished: the tree is outside every
working copy, every slot has a `.gitignore` containing `*`, and this
repository's own `.gitignore` covers `game-files/`, `gamedata/`, `GAMES/` plus
the data extensions.

## Style

- Standard library first; `pathlib` over `os.path`; type hints on public
  functions; dataclasses for records.
- Keep the CLI honest: exit code `2` for usage errors, non-zero for "nothing
  found", `0` for success.
- Never print file contents. Print sizes, counts, offsets and hashes.

## Commits and PRs

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). One topic
per PR; research changes and code changes in separate PRs when possible.
`CHANGELOG.md` gets an entry under `## [Unreleased]` for user-visible changes.

## Local checks before pushing

```bash
python -m compileall -q src tests
python -m pytest tests -m "not realgame" -q
grep -rn "LOMAX.GAME\|\.WLD" --include="*.py" tests | head   # sanity: fixtures only
git status --short
```
