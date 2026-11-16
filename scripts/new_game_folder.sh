#!/usr/bin/env bash
# Create a local-only game-files slot for a repository.
#
#   scripts/new_game_folder.sh <repository-name> [variant ...]
#
# Example:
#   scripts/new_game_folder.sh lomax-modern pc-retail pc-disc
#
# The slot is created NEXT TO the repository, never inside it:
#   $HOME/projects/game-files/<repository-name>/<variant>/
# so nothing in it can be staged, committed or pushed. The script refuses to
# run if the target would end up inside a git working tree.
set -euo pipefail

repo_name="${1:-}"
if [[ -z "$repo_name" ]]; then
  echo "usage: $0 <repository-name> [variant ...]" >&2
  exit 2
fi
shift

if [[ $# -eq 0 ]]; then
  set -- pc-retail
fi

projects_root="${PROJECTS_ROOT:-$HOME/projects}"
slot_root="$projects_root/game-files/$repo_name"

created=0
if [[ ! -d "$slot_root" ]]; then
  mkdir -p "$slot_root"
  created=1
fi

# The guarantee: the slot must not be reachable from any git working tree.
if toplevel=$(git -C "$slot_root" rev-parse --show-toplevel 2>/dev/null); then
  echo "error: $slot_root is inside the git working tree $toplevel; refusing" >&2
  if [[ "$created" == "1" ]]; then
    # Remove the directories this run created, and their parents while empty.
    rmdir -p "$slot_root" 2>/dev/null || true
  fi
  exit 1
fi

ignore_file="$slot_root/.gitignore"
if [[ ! -f "$ignore_file" ]]; then
  printf '# Local game data: never commit, never publish.\n*\n!.gitignore\n' \
    > "$ignore_file"
fi

for variant in "$@"; do
  variant_dir="$slot_root/$variant"
  mkdir -p "$variant_dir"
  if [[ ! -f "$variant_dir/.gitignore" ]]; then
    printf '# Local game data: never commit, never publish.\n*\n!.gitignore\n' \
      > "$variant_dir/.gitignore"
  fi
  echo "created $variant_dir"
done

cat <<EOF

Next steps:
  1. copy your files into the variant folder(s)
  2. export the environment variable the project documents, e.g.
       export LOMAX_GAME_DIR="$slot_root/${1:-pc-retail}"
  3. verify nothing can be published:
       git -C "$slot_root" rev-parse --show-toplevel   # must fail
EOF
