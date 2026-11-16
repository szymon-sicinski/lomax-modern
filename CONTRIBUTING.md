# Contributing

Thanks for helping. This project is research-first, so documentation and
measurements are as welcome as code.

## Good first contributions

- **Confirm or refute a format claim.** Run `lomax-modern wldscan` on your own
  `WORLDS/*.WLD` files and open an issue with the *summary only* (tag list,
  layout hypothesis, whether the chain reached EOF). Do **not** attach game
  files or hex dumps of large regions.
- **Answer an open question** from
  [`docs/research/05-open-questions.md`](docs/research/05-open-questions.md).
- **Platform reports.** Distro, Wine/Proton version, wrapper, what fails. No
  binaries, no logs containing game data.
- **Fix a citation.** If a source says something different from what we claim,
  that is a bug — please report it.

## Reporting bugs

Include: command, expected vs actual, Python version, OS, and the text output.
Never attach the game, disc images, extracted assets, or full file hashes.

## Pull requests

1. One topic per PR; keep research and code changes separate where practical.
2. Tests: unit tests must not need game files. If a test needs them, it belongs
   in `tests/integration/` behind `LOMAX_GAME_DIR` and must skip cleanly.
3. Run before pushing:
   ```bash
   python -m compileall -q src tests
   python -m pytest tests -m "not realgame" -q
   ```
4. Update docs and `CHANGELOG.md` in the same PR.
5. Conventional Commit messages (`docs:`, `feat:`, `fix:`, `test:`).

## Legal ground rules for contributions

By contributing you confirm that:

- You wrote the code, or it comes from a source whose licence permits inclusion
  (state which).
- You are **not** submitting code, data, prose or assets from `Lomax+` or any
  other unlicensed project.
- You are not submitting game data, disc images, extracted art, music, or
  binaries of any kind.
- Any upscaled/derived art stays out of the repository.

## Code of conduct

Be accurate, cite sources, and assume the other person is trying to get the
game working on a 2020s machine. Disagreements about facts are settled with
evidence in the repo, not with confidence.
