#!/usr/bin/env bash
#
# examples/demo.sh -- walk the whole 0.4.0-alpha capability in order, against
# your own unpacked copy of The Adventures of Lomax.
#
#   bash examples/demo.sh "<install>" [--out DIR]
#
# <install> is a folder in the retail layout (LOMAX.EXE, WORLDS/*.WLD, SFX/,
# AMBIENT/, JINGLES/, DEMOS/).  This script ships no game data: it reads your
# copy in place and writes every output into DIR (default ./demo-out), never
# into the game folder.
#
# It stops at the first failing command (set -euo pipefail) and prints each
# command before running it, so the terminal transcript is the demo.
#
# No dependencies beyond the package itself and python3.
set -euo pipefail

prog=$(basename -- "$0")

usage() {
  cat <<EOF
usage: $prog <install> [--out DIR]

  <install>   an unpacked Lomax folder in the retail layout
              (LOMAX.EXE, WORLDS/*.WLD, SFX/, AMBIENT/, JINGLES/, DEMOS/)
  --out DIR   where every output goes (default: ./demo-out)

Read-only on <install>.  Runs, in order:
  doctor -> present --modern -> present --authentic -> slice --frames
  -> gif -> conformance -> export
EOF
}

install=""
out="./demo-out"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --out)
      if [ "$#" -lt 2 ]; then
        echo "$prog: error: --out needs a directory" >&2
        exit 2
      fi
      out=$2
      shift 2
      ;;
    --out=*)
      out=${1#--out=}
      shift
      ;;
    -*)
      echo "$prog: error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [ -n "$install" ]; then
        echo "$prog: error: only one <install> path, got '$install' and '$1'" >&2
        exit 2
      fi
      install=$1
      shift
      ;;
  esac
done

if [ -z "$install" ]; then
  echo "$prog: error: missing <install> -- the path to your own unpacked copy" >&2
  usage >&2
  exit 2
fi

if [ ! -d "$install" ]; then
  echo "$prog: error: not a directory: $install" >&2
  exit 2
fi

# Run the checkout's own code when there is a checkout, so the demo always
# exercises the tree it sits in; otherwise use the installed entry point.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(dirname -- "$here")

if [ -f "$repo_root/src/lomax_modern/cli.py" ]; then
  export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
  CLI=(python3 -m lomax_modern)
elif command -v lomax-modern >/dev/null 2>&1 &&
  python3 -c 'import lomax_modern' >/dev/null 2>&1; then
  CLI=(lomax-modern)
else
  echo "$prog: error: cannot find lomax_modern" >&2
  echo "hint: pip install -e .  (see docs/runbook.md, section 2)" >&2
  exit 2
fi

step() {
  printf '\n== %s ==\n' "$1"
}

# Print the command, then run it: the transcript is the demo.
run() {
  printf '$'
  printf ' %q' "$@"
  printf '\n'
  "$@"
}

step "1/7  doctor -- what is in your copy (read-only)"
run "${CLI[@]}" doctor "$install"

step "2/7  present --modern -- one engine frame, epx-aa, 4x into 1920x1080"
run "${CLI[@]}" present "$install" --world VILLAGE --modern \
  --config "$out/config.json" --frame "$out/frame-modern.png"

step "3/7  present --authentic -- the same frame, native 320x240, nearest"
run "${CLI[@]}" present "$install" --world VILLAGE --authentic \
  --config "$out/config.json" --frame "$out/frame-authentic.png"

step "4/7  slice --frames 120 -- one PNG per 60 Hz tick (2 s of engine time)"
run "${CLI[@]}" slice "$install" --world VILLAGE --frames 120 \
  --out "$out/frames"

step "5/7  gif -- fold the frame sequence into one looping GIF89a"
run "${CLI[@]}" gif "$out/frames" --out "$out/demo.gif" --fps 60

step "6/7  conformance -- the render harness (no display, no game data)"
run python3 -m lomax_modern.conformance

step "7/7  export -- decode VILLAGE.WLD into tile and collision sheets"
run "${CLI[@]}" export "$install/WORLDS/VILLAGE.WLD" --out "$out/art"

step "done -- outputs are in $out, nothing was written into $install"
for artifact in \
  frame-modern.png \
  frame-authentic.png \
  demo.gif \
  frames/frame_0000.png \
  frames/frame_0119.png \
  art/village_cells.png \
  art/village_tiles_plane00.png; do
  if [ -e "$out/$artifact" ]; then
    printf '  %s\n' "$out/$artifact"
  fi
done
