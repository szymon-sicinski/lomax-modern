"""Tests for ``scripts/token_cost_report.py`` (synthetic logs and DB only).

The script reads the kanban DB and per-profile ``logs/agent.log``; both are
rebuilt here from synthetic data so the cache/fresh split is checked against a
known answer rather than a real board.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "token_cost_report.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("token_cost_report", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _log_line(session: str, call: int, model: str, tin: int, tout: int, cached: int) -> str:
    return (
        f"2026-11-18 13:47:12,947 INFO [{session}] agent.conversation_loop: "
        f"API call #{call}: model={model} provider=deepseek in={tin} out={tout} "
        f"total={tin + tout} cache={cached}/{tin}\n"
    )


def _write_logs(root: Path, profile: str, lines: list[str]) -> None:
    logdir = root / profile / "logs"
    logdir.mkdir(parents=True)
    (logdir / "agent.log").write_text("".join(lines), encoding="utf-8")


def _make_db(path: Path, rows: list[tuple[str, str, str]]) -> None:
    """rows: (task_id, title, worker_session_id)."""
    conn = sqlite3.connect(path)
    conn.execute(
        "create table tasks (id text primary key, title text, assignee text, status text, "
        "priority integer, created_by text, created_at integer, started_at integer, "
        "completed_at integer, workspace_kind text, workspace_path text, branch_name text, "
        "project_id text, claim_lock text, claim_expires integer, tenant text, result text, "
        "idempotency_key text, consecutive_failures integer, worker_pid integer, "
        "worker_started_at integer, last_failure_error text, max_runtime_seconds integer, "
        "last_heartbeat_at integer, current_run_id integer, workflow_template_id text, "
        "current_step_key text, skills text, model_override text, provider_override text, "
        "reasoning_effort text, max_retries integer, goal_mode integer, goal_max_turns integer, "
        "session_id text, block_kind text, block_recurrences integer, completion_contract text)"
    )
    conn.execute(
        "create table task_runs (id integer primary key, task_id text, profile text, step_key text, "
        "status text, claim_lock text, claim_expires integer, worker_pid integer, "
        "worker_started_at integer, max_runtime_seconds integer, last_heartbeat_at integer, "
        "started_at integer, ended_at integer, outcome text, summary text, metadata text, error text)"
    )
    for i, (task_id, title, session) in enumerate(rows):
        conn.execute(
            "insert into tasks (id, title, assignee, status) values (?, ?, ?, ?)",
            (task_id, title, "builder", "done"),
        )
        conn.execute(
            "insert into task_runs (id, task_id, profile, metadata) values (?, ?, ?, ?)",
            (i + 1, task_id, "builder", json.dumps({"worker_session_id": session})),
        )
    conn.commit()
    conn.close()


def test_parse_logs_splits_cached_from_fresh(tmp_path: Path) -> None:
    tcr = _load()
    _write_logs(
        tmp_path,
        "builder",
        [
            _log_line("local-aaaa", 1, "deepseek-v4-pro", 1000, 50, 900),
            _log_line("local-aaaa", 2, "deepseek-v4-pro", 2000, 100, 1900),
        ],
    )
    _write_logs(tmp_path, "scout", [_log_line("local-bbbb", 1, "deepseek-flash", 500, 20, 450)])

    sessions = tcr.parse_logs(tmp_path)

    a = sessions["local-aaaa"]
    assert (a["in"], a["out"], a["calls"], a["cached"]) == (3000, 150, 2, 2800)
    assert a["profile"] == "builder"
    assert a["models"]["deepseek-v4-pro"] == [3000, 150, 2, 2800]

    b = sessions["local-bbbb"]
    assert (b["in"], b["out"], b["calls"], b["cached"]) == (500, 20, 1, 450)
    assert b["models"]["deepseek-flash"] == [500, 20, 1, 450]


def test_missing_cache_field_counts_zero_cached(tmp_path: Path) -> None:
    tcr = _load()
    # A line without the cache= field must not crash and counts cached=0.
    _write_logs(
        tmp_path,
        "builder",
        ["2026-11-18 13:47:12,947 INFO [local-cccc] agent.conversation_loop: "
         "API call #1: model=deepseek-v4-pro provider=deepseek in=100 out=10 total=110\n"],
    )
    sessions = tcr.parse_logs(tmp_path)
    c = sessions["local-cccc"]
    assert (c["in"], c["cached"]) == (100, 0)


def test_main_reports_cached_and_fresh(tmp_path: Path) -> None:
    tcr = _load()
    _write_logs(
        tmp_path,
        "builder",
        [
            _log_line("local-aaaa", 1, "deepseek-v4-pro", 1000, 50, 900),
            _log_line("local-aaaa", 2, "deepseek-v4-pro", 2000, 100, 1900),
        ],
    )
    db = tmp_path / "kanban.db"
    _make_db(db, [("t_1", "LMX-10 M2: decode the MAP chunk", "local-aaaa")])

    code = tcr.main(["--db", str(db), "--logs-dir", str(tmp_path), "--json"])
    assert code == 0

    # json is the last stdout line; capture via monkeypatch-free subprocess-like check
    # by re-running through the module with capsys is overkill here — assert on the
    # pure aggregation instead by calling main's building blocks is avoided; simplest
    # is to check the total through a captured print.
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = tcr.main(["--db", str(db), "--logs-dir", str(tmp_path), "--json"])
    assert code == 0
    out = json.loads(buf.getvalue())

    assert out["total"]["in"] == 3000
    assert out["total"]["out"] == 150
    assert out["total"]["cached"] == 2800
    assert out["total"]["fresh"] == 200
    assert out["cards_measured"] == 1
    assert out["cards"][0]["cached"] == 2800
    assert out["cards"][0]["fresh"] == 200
    assert out["by_model"]["deepseek-v4-pro"]["cached"] == 2800
