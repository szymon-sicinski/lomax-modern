"""Tests for the P5 install gate (synthetic layout only).

The gate is what makes ``present`` safe to hand to someone who owns the data but
has copied it to the wrong place: every failure prints which entry is missing,
not "cannot find its data".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lomax_modern.install import (
    EXPECTED_DIRS,
    REQUIRED_FILES,
    check_install,
    is_inside_tree,
    resolve_world,
)
from tests.fixtures.install import build_install


def test_complete_install_passes_and_lists_every_entry(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game")

    manifest = check_install(root)

    assert manifest.ok
    assert manifest.root == root
    assert manifest.missing_required == ()
    assert manifest.missing_expected == ()
    names = [entry.name for entry in manifest.entries]
    assert names == [
        "WORLDS/",
        "SFX/",
        "AMBIENT/",
        "JINGLES/",
        "DEMOS/",
        "LOMAX.EXE",
        "GAME.TXT",
    ]
    assert len(manifest.world_files) == 1
    assert manifest.world_files[0].name == "VILLAGE.WLD"
    assert "complete unpacked install" in manifest.verdict()


def test_manifest_is_file_by_file_and_hash_free(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game")

    text = check_install(root).format()

    assert "WORLDS/" in text
    assert "VILLAGE.WLD" in text
    assert "LOMAX.EXE" in text and "unused by the engine" in text
    assert "SFX/" in text
    # Names, counts and sizes only: a 64-hex digest would violate the repo rule.
    assert not re.search(r"[0-9a-f]{64}", text)
    # No file contents, even when the tree has a text file.
    assert "synthetic marker file" not in text


def test_missing_worlds_folder_fails_with_the_entry_named(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game", worlds_dir="WORLDS")
    for child in (root / "WORLDS").iterdir():
        child.unlink()
    (root / "WORLDS").rmdir()

    manifest = check_install(root)

    assert not manifest.ok
    assert "WORLDS/" in manifest.missing_required
    assert "not an unpacked Lomax game directory" in manifest.verdict()
    lines = manifest.format().splitlines()
    assert any(
        line.startswith("  WORLDS/") and "MISSING" in line for line in lines
    )


def test_empty_worlds_folder_fails_with_the_world_set_named(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game", worlds=())

    manifest = check_install(root)

    assert not manifest.ok
    assert "WORLDS/*.WLD" in manifest.missing_required
    assert "WORLDS/*.WLD" in manifest.format()


def test_missing_executable_fails(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game")
    (root / "LOMAX.EXE").unlink()

    manifest = check_install(root)

    assert not manifest.ok
    assert "LOMAX.EXE" in manifest.missing_required


def test_missing_optional_folders_run_but_say_incomplete(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game", dirs=())

    manifest = check_install(root)

    assert manifest.ok
    assert set(manifest.missing_expected) == set(name + "/" for name in EXPECTED_DIRS)
    assert "incomplete optional entries" in manifest.verdict()
    assert "the presenter still runs" in manifest.verdict()


def test_nested_install_root_is_resolved_one_level_down(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    nested = build_install(slot / "LOMAX")

    manifest = check_install(slot)

    assert manifest.ok
    assert manifest.root == nested
    assert manifest.requested_root == slot
    assert "one level down" in manifest.format()
    assert f"requested: {slot}" in manifest.format()


def test_two_candidate_subdirectories_are_ambiguous_not_guessed(
    tmp_path: Path,
) -> None:
    slot = tmp_path / "slot"
    build_install(slot / "COPY-A")
    build_install(slot / "COPY-B")

    manifest = check_install(slot)

    assert not manifest.ok
    assert any(note.startswith("ambiguous:") for note in manifest.notes)
    assert "COPY-A/" in manifest.format() and "COPY-B/" in manifest.format()


def test_file_path_is_refused_with_a_reason(tmp_path: Path) -> None:
    target = tmp_path / "not-a-folder"
    target.write_text("x", encoding="utf-8")

    manifest = check_install(target)

    assert not manifest.ok
    assert manifest.entries == ()
    assert "not a directory" in manifest.format()
    assert "missing: " not in manifest.verdict()


def test_missing_path_is_refused(tmp_path: Path) -> None:
    manifest = check_install(tmp_path / "nowhere")

    assert not manifest.ok
    assert "not a directory" in manifest.format()


def test_layout_names_are_case_insensitive(tmp_path: Path) -> None:
    root = build_install(
        tmp_path / "game",
        worlds_dir="worlds",
        exe="lomax.exe",
        dirs=("sfx", "ambient", "jingles", "demos"),
    )

    manifest = check_install(root)

    assert manifest.ok
    assert manifest.worlds_dir is not None
    assert manifest.worlds_dir.name == "worlds"
    assert resolve_world(manifest).name == "VILLAGE.WLD"


def test_resolve_world_is_case_insensitive_and_actionable(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game", worlds=("VILLAGE", "HAUNTED"))
    manifest = check_install(root)

    assert resolve_world(manifest, "haunted").name == "HAUNTED.WLD"
    assert resolve_world(manifest, "HAUNTED.WLD").name == "HAUNTED.WLD"
    # No --world: the slice command's start (VILLAGE), not the first alphabetically.
    assert resolve_world(manifest).name == "VILLAGE.WLD"

    with pytest.raises(LookupError) as caught:
        resolve_world(manifest, "BONUS")
    assert "VILLAGE" in str(caught.value) and "HAUNTED" in str(caught.value)


def test_resolve_world_falls_back_to_the_first_file(tmp_path: Path) -> None:
    root = build_install(tmp_path / "game", worlds=("HAUNTED", "WEST"))
    manifest = check_install(root)

    assert resolve_world(manifest).name == "HAUNTED.WLD"


def test_resolve_world_without_worlds_names_the_folder(tmp_path: Path) -> None:
    manifest = check_install(build_install(tmp_path / "game", worlds=()))

    with pytest.raises(LookupError, match=r"no \*\.WLD"):
        resolve_world(manifest)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("game", True),
        ("game/WORLDS/VILLAGE.WLD", True),
        ("game-other", False),
    ],
)
def test_is_inside_tree(tmp_path: Path, candidate: str, expected: bool) -> None:
    root = build_install(tmp_path / "game")
    (tmp_path / "game-other").mkdir()

    assert is_inside_tree(tmp_path / candidate, root) is expected


def test_required_files_constant_lists_the_executable() -> None:
    # The engine never runs LOMAX.EXE; its presence is the retail-install proof.
    assert REQUIRED_FILES == ("LOMAX.EXE",)
