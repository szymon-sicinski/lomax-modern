#!/usr/bin/env python3
"""Measure what the agents actually spent, from the only source that records it.

The board stores wall-clock and card/review counts; it does **not** store token
usage.  The token counts do exist, one line per model call, in each profile's
``logs/agent.log``::

    ... INFO [local-<session>] agent.conversation_loop: API call #7:
        model=deepseek-v4-pro provider=deepseek in=46182 out=51 total=46233 ...

and the board links a card to a session: ``task_runs.metadata.worker_session_id``
holds the same ``local-<session>`` id.  Join the two and a card's cost becomes
measurable instead of estimated.

Usage::

    python3 token_cost_report.py --board retrolab
    python3 token_cost_report.py --board retrolab --milestone M4 --json

Read-only: it opens the kanban DB with ``mode=ro`` and only reads logs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

def _hermes_home() -> Path:
    """~/.hermes on the host; $HERMES_HOME or /workspace inside the sandbox."""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    home = Path.home() / ".hermes"
    if home.exists():
        return home
    return Path("/workspace") if Path("/workspace/kanban").exists() else home


HERMES_HOME = _hermes_home()
DEFAULT_BOARDS = {
    "retrolab": HERMES_HOME / "kanban/boards/retrolab/kanban.db",
    "default": HERMES_HOME / "kanban.db",
}

# 2026-11-18 13:47:12,947 INFO [local-3f2a...] agent.conversation_loop: API call #46: model=deepseek-v4-pro provider=deepseek in=188200 out=475 total=188675
CALL = re.compile(
    r"\[(?P<session>local-[0-9a-f]+)\].*API call #\d+: model=(?P<model>\S+) "
    r"provider=(?P<provider>\S+) in=(?P<in>\d+) out=(?P<out>\d+) total=(?P<total>\d+)"
)
MILESTONE = re.compile(r"\bM(?P<m>[2-9])\b", re.I)
LMX_TAG = re.compile(r"\bLMX-(?P<lmx>\d+)\b", re.I)
CACHE = re.compile(r"cache=(?P<cached>\d+)/(?P<ctx>\d+)")


def parse_logs(logs_dir: Path) -> dict[str, dict]:
    """session id -> {in, out, calls, cached} and per-model [in, out, calls, cached].

    ``cached`` is summed from each line's ``cache=<cached>/<context>`` field;
    ``fresh = in - cached`` is the part actually billed at the miss rate.
    """
    sessions: dict[str, dict] = defaultdict(
        lambda: {"in": 0, "out": 0, "calls": 0, "cached": 0,
                 "models": defaultdict(lambda: [0, 0, 0, 0])}
    )
    for path in sorted(logs_dir.glob("*/logs/agent.log")):
        profile = path.parent.parent.name
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = CALL.search(line)
                if not match:
                    continue
                cm = CACHE.search(line)
                cached = int(cm.group("cached")) if cm else 0
                entry = sessions[match["session"]]
                tin, tout = int(match["in"]), int(match["out"])
                entry["in"] += tin
                entry["out"] += tout
                entry["calls"] += 1
                entry["cached"] += cached
                entry["profile"] = profile
                bucket = entry["models"][match["model"]]
                bucket[0] += tin
                bucket[1] += tout
                bucket[2] += 1
                bucket[3] += cached
    return sessions


def parse_runs(db: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = []
    for run in conn.execute("select id, task_id, profile, started_at, ended_at, outcome, metadata from task_runs"):
        session = ""
        try:
            meta = json.loads(run["metadata"] or "{}")
            session = str(meta.get("worker_session_id") or "")
        except ValueError:
            pass
        title = ""
        row = conn.execute("select title from tasks where id=?", (run["task_id"],)).fetchone()
        if row:
            title = row["title"]
        rows.append({
            "run_id": run["id"],
            "task_id": run["task_id"],
            "title": title,
            "profile": run["profile"],
            "session": session,
            "started_at": run["started_at"],
            "ended_at": run["ended_at"],
            "outcome": run["outcome"],
        })
    conn.close()
    return rows


def milestone_of(title: str) -> str:
    """M4 beats LMX-10: the milestone marker is what the budget allocates by."""
    marker = MILESTONE.search(title)
    if marker:
        return f"M{marker.group('m')}"
    tag = LMX_TAG.search(title)
    return f"LMX-{tag.group('lmx')}" if tag else "other"


def _usage_row(in_: int, out: int, calls: int, cached: int) -> dict:
    return {"in": in_, "out": out, "calls": calls, "cached": cached, "fresh": in_ - cached}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default="retrolab", choices=sorted(DEFAULT_BOARDS))
    parser.add_argument("--db", default=None, help="override the kanban DB path")
    parser.add_argument("--logs-dir", default=str(HERMES_HOME / "profiles"))
    parser.add_argument("--milestone", default=None, help="only rows for this milestone (e.g. M4)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    db = Path(args.db) if args.db else DEFAULT_BOARDS[args.board]
    if not db.exists():
        parser.error(f"no kanban DB at {db}")
    sessions = parse_logs(Path(args.logs_dir))
    runs = parse_runs(db)

    by_task: dict[str, dict] = {}
    unmatched = 0
    for run in runs:
        usage = sessions.get(run["session"])
        if usage is None:
            unmatched += 1
            continue
        prev = by_task.get(run["task_id"])
        if prev is None:
            by_task[run["task_id"]] = {
                "task_id": run["task_id"], "title": run["title"], "profile": run["profile"],
                "milestone": milestone_of(run["title"]),
                "in": usage["in"], "out": usage["out"], "calls": usage["calls"],
                "cached": usage["cached"],
            }
        else:  # a card retried: several sessions, same task
            prev["in"] += usage["in"]
            prev["out"] += usage["out"]
            prev["calls"] += usage["calls"]
            prev["cached"] += usage["cached"]

    for row in by_task.values():
        row["fresh"] = row["in"] - row["cached"]

    by_milestone: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "cached": 0, "cards": 0})
    by_profile: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "cached": 0, "cards": 0})
    by_model: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # [in, out, calls, cached]
    for task_id, row in by_task.items():
        for bucket in (by_milestone[row["milestone"]], by_profile[row["profile"]]):
            bucket["in"] += row["in"]
            bucket["out"] += row["out"]
            bucket["calls"] += row["calls"]
            bucket["cached"] += row["cached"]
            bucket["cards"] += 1
        usage = sessions.get(next((r["session"] for r in runs if r["task_id"] == task_id), ""), None)
        if usage:
            for model, (tin, tout, calls, cached) in usage["models"].items():
                by_model[model][0] += tin
                by_model[model][1] += tout
                by_model[model][2] += calls
                by_model[model][3] += cached

    total = _usage_row(
        sum(r["in"] for r in by_task.values()),
        sum(r["out"] for r in by_task.values()),
        sum(r["calls"] for r in by_task.values()),
        sum(r["cached"] for r in by_task.values()),
    )

    result = {
        "board": args.board,
        "cards_measured": len(by_task),
        "runs_without_log": unmatched,
        "total": total,
        "by_milestone": {k: dict(v) for k, v in sorted(by_milestone.items())},
        "by_profile": {k: dict(v) for k, v in sorted(by_profile.items())},
        "by_model": {k: _usage_row(v[0], v[1], v[2], v[3]) for k, v in by_model.items()},
        "cards": sorted(by_task.values(), key=lambda r: -r["in"]),
    }
    if args.milestone:
        keep = args.milestone.upper()
        result["cards"] = [r for r in result["cards"] if r["milestone"] == keep]

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    ratio = total["cached"] / total["in"] if total["in"] else 0.0
    print(f"board: {args.board}   cards measured: {len(by_task)}   runs without a matching log: {unmatched}")
    print(f"input processed: {total['in']:,}  (cached {total['cached']:,} = {ratio:.1%}, "
          f"fresh {total['fresh']:,})")
    out_line = f"output: {total['out']:,}  over {total['calls']:,} model calls"
    if total["out"]:
        out_line += f"  fresh:output = {total['fresh'] / total['out']:.2f}:1"
    print(out_line)
    print()
    print(f"{'milestone':10s} {'cards':>5s} {'input':>12s} {'cached':>12s} {'fresh':>10s} {'output':>10s} {'calls':>7s}")
    for name, row in result["by_milestone"].items():
        print(f"{name:10s} {row['cards']:5d} {row['in']:12,} {row['cached']:12,} "
              f"{row['in'] - row['cached']:10,} {row['out']:10,} {row['calls']:7,}")
    print()
    print(f"{'profile':10s} {'cards':>5s} {'input':>12s} {'cached':>12s} {'output':>10s}")
    for name, row in result["by_profile"].items():
        print(f"{name:10s} {row['cards']:5d} {row['in']:12,} {row['cached']:12,} {row['out']:10,}")
    print()
    print(f"{'model':26s} {'input':>12s} {'cached':>12s} {'output':>10s} {'calls':>7s}")
    for name, row in sorted(result["by_model"].items(), key=lambda kv: -kv[1]["in"]):
        print(f"{name:26s} {row['in']:12,} {row['cached']:12,} {row['out']:10,} {row['calls']:7,}")
    print()
    print("most expensive cards:")
    for row in result["cards"][:8]:
        print(f"  {row['in']:9,} in {row['out']:8,} out  {row['milestone']:5s} {row['title'][:58]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
