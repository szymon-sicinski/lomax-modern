# Examples

- `scale_math.py` — reproduces every number quoted in
  [`docs/research/02-resolution.md`](../docs/research/02-resolution.md)
  (widescreen candidates, fade-surface rounding, presentation scale factors,
  internal render multipliers). Pure standard library, no game files:

  ```bash
  python examples/scale_math.py
  ```

- `scale_demo.py` — side-by-side demonstration of the presenter's two filters
  (`nearest` vs `epx-aa`) on a generated 16x16 sprite, rendered from
  `lomax_modern.scaler` at an integer factor. Prints ASCII panels in indexed
  mode so the difference is visible in a terminal and in a diff, and writes a
  truecolour PNG (stdlib `zlib`, no Pillow) where the anti-aliasing shows:

  ```bash
  python examples/scale_demo.py
  python examples/scale_demo.py --scale 6 --png /tmp/scale_demo.png
  ```

- `demo.sh` — the whole alpha in one run: `doctor` → `present --modern` →
  `present --authentic` → `slice --frames` → `gif` → `conformance` → `export`,
  against your own unpacked copy, printing each command before it runs. Fails at
  the first refusal and writes only to `./demo-out` (or `--out DIR`). The
  transcript is reproduced command by command in
  [`docs/demo.md`](../docs/demo.md):

  ```bash
  bash examples/demo.sh "<install>"
  ```

More examples will land with the `WLD` toolkit (LMX-5/LMX-6): a chunk dump, a
tile export, and a round-trip check.
