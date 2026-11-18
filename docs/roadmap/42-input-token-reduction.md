# 42. Input-token reduction — where the 219M goes, and what reduces it

[`41-measured-cost.md`](41-measured-cost.md) measured what the M2–M4 work
consumed and produced a headline of **219.5M input tokens over 2.4M output —
91:1**. The operator's verdict on that ratio was "unacceptable". This file is
the follow-up: it splits that number into *processed* vs *billed*, puts a money
figure on each part, measures what actually drives the remainder, and ranks
interventions by measured effect. The headline conclusion is **the 91:1 is an
accounting artifact, and there is nothing expensive left to fix.**

Every figure names its source: the operator's split is from the cache-aware
re-run of [`scripts/token_cost_report.py`](../../scripts/token_cost_report.py)
on board `retrolab` (2026-11-18); card-level numbers come from the board DB
(`task_runs`, `task_events`) and [`41-measured-cost.md`](41-measured-cost.md).

## 1. The split: processed vs billed

The 219.5M input figure counts **tokens processed**, and 97.3 % of them were
served from the provider cache. The per-call `cache=<cached>/<context>` field
says so:

| | tokens | share |
|---|---:|---:|
| input processed | 221,747,051 | 100 % |
| of which cached | 215,817,088 | **97.3 %** |
| of which fresh | 5,929,963 | 2.7 % |
| output | 2,437,509 | — |
| **fresh input : output** | **2.43 : 1** | |

*(Source: cache-aware `token_cost_report.py --board retrolab --json`, 2026-11-18;
the by-milestone attribution in 41-measured-cost.md totals 219.5M — the ~2.2M
delta is the cache parse capturing ~1 % more input than the older by-milestone
pass.)*

So "91 input tokens per output token" is an artifact of counting cache hits as
input. The ratio that drives prompt-processing cost is **2.4 fresh tokens per
output token** — ordinary for agentic work.

## 2. The money: what the cached bill actually is

[`40-budget.md`](40-budget.md) prices input and output at derived rates; this
section applies the cache discount and the model mix to get a dollar figure.
DeepSeek's V4 price list (Oct–Nov 2026, off-peak, per 1M tokens) is the anchor:

| model | input cache-miss | input cache-hit | output | hit:miss |
|---|---:|---:|---:|---:|
| `deepseek-v4-pro` | $0.66 | $0.022 | $1.98 | **30×** |
| `deepseek-flash` | $0.15 | $0.003 | $0.60 | **50×** |

*(Peak is 2× off-peak. 40-budget's derived `@pro` output rate $3.40 sits between
the off-peak $1.98 and peak $3.96 — its calibration was peak-influenced.)*

Model mix from 41-measured-cost.md: `deepseek-v4-pro` 127.0M in / 1.66M out,
`deepseek-flash` 90.8M in / 710k out, plus ~3.9M in / 67k out unattributed
(charged here at the pro rate as a conservative upper bound). Applying the
97.3 % cache ratio uniformly:

| component | tokens | money (off-peak) | share of money |
|---|---:|---:|---:|
| fresh input | 5,929,963 | $2.68 | 28 % |
| cached input | 215,817,088 | $3.07 | **32 %** |
| output | 2,437,509 | $3.85 | **40 %** |
| **total** | | **~$9.59** | |

The naive reading — every input token at the full miss rate, which is what the
"91:1 unacceptable" framing implied — would be **~$103.89**. The cache-aware
figure is **~$9.59, i.e. 9.2 % of the naive number**. Peak doubles it to ~$19.

Three consequences:

1. **Output, not input, is the largest money line (40 %).** Output was also the
   *best-estimated* line — 41-measured-cost.md found M2 landed within 0.4 % and
   M4 within 8 % of the 40-budget estimate. Output is "work actually produced";
   it is not waste to cut.
2. **The cached bill is real but ~$3.** It is the second line, not a rounding
   error, and it scales as `calls × context` — but at a 30–50× hit discount it
   is cheap. 41-measured-cost.md's "roughly an order of magnitude below fresh"
   understates the discount: the provider ratio is 30× (pro) and 50× (flash),
   so the cached bill is *smaller* than that doc implies.
3. **The remaining lever on the cached line is `calls × context`, and it is a
   latency/wall-clock problem more than a money problem.** $3 is the whole
   cached line for M2–M4; halving it saves ~$1.50. The same reduction, though,
   halves the tokens re-read every call, which is what makes long cards slow.

## 3. Where the cached volume comes from: `calls × context`

The 215.8M cached tokens decompose cleanly:

| term | value | source |
|---|---:|---|
| model calls | 2,374 | 41-measured-cost.md total |
| cards measured | 58 | 41-measured-cost.md |
| avg calls / card | 40.9 | 2,374 ÷ 58 |
| avg cached context / call | **90,909** | 215,817,088 ÷ 2,374 |
| tail context (long cards) | 150k–190k | 41-measured-cost.md |

So the cached volume is **2,374 calls × ~91k average context**, and the
spread per milestone shows *where* the context grows:

| milestone | cards | calls/card | input/card | input/call |
|---|---:|---:|---:|---:|
| M2 data layer | 6 | 75.5 | 9.47M | 125k |
| M3 engine core | 2 | 58.5 | 9.10M | **156k** |
| M4 presenter | 14 | 42.7 | 4.06M | 95k |
| LMX-7 research | 10 | 44.7 | 4.03M | 90k |

M3 (the one genuinely unfamiliar milestone) has the highest input per call
(156k) — consistent with its widest rework band in 40-budget. M2 has the most
calls per card (75.5). Both are "few big cards" milestones; M4 is "many small
cards" and pays less input per card.

### The fixed cost of a spawned worker (the floor every card pays)

The board records **spawns** (`task_runs`), which is the multiplier on that
floor. (Population note: the token numbers in §1–§3 are the **58-card measured
subset** from 41-measured-cost.md — cards with a matching log session. This
subsection and §4 use the **board-wide** population, 73 tasks / 94 runs, which
is the right one for spawn and waste accounting: the 15 extra tasks are the
ones whose runs predate the log window or were infra-blocked.)

| spawns per card | cards |
|---:|---:|
| 1 | 63 |
| 2 | 5 |
| 3 | 3 |
| 5 | 1 |
| 7 | 1 |

**63 of 73 cards spawned exactly once**; the average is **1.29 runs/card**
(94 runs over 73 tasks). Each spawn re-pays the system prompt, the loaded
skills, `AGENTS.md`, and the card body before any work happens — but that floor
is paid *once* for nearly every card. Card granularity is already near its
minimum; splitting or merging cards will not move the fixed cost.

The context-at-call-#1 number itself (the absolute size of that floor) cannot
be read from the board — it is the `in=` on a session's first API call, which
lives in the host `logs/agent.log`, not the DB. See §7.

## 4. Measured drivers — what the board itself shows

### 4.1 Retries and non-completion: the only genuine waste

Run outcomes across the board:

| outcome | runs |
|---|---:|
| completed | 69 |
| blocked | 15 |
| spawn_failed | 4 |
| gave_up | 2 |
| crashed | 2 |

**23 of 94 runs (24 %) ended without completing.** Three cards account for
almost all of the dispatcher's respawn-guard churn — `t_cb2f724c` (583 guards,
duplicate-twin confusion, 2 blocked + 1 completed), `t_ef9f28da` (156 guards,
2 spawn-failed on a data-access blocker), `t_9ede11a8` (57 guards, 4 blocked on
git/credentials) — 796 guard events in total. Every blocked/re-spawned run
re-pays the fixed context and re-grows it. This is the one place where "fewer
calls" is both cheap and already measured: the failures were **infrastructure**
(no `GITHUB_TOKEN` in the container, no game-data mount, a duplicate card), not
agent discipline.

### 4.2 Model routing is already correct

Profiles → model by the 40-budget routing table, checked against the token
attribution in 41-measured-cost.md:

| profile | model | input | output |
|---|---|---:|---:|
| builder + scout | `deepseek-flash` | 90.8M | 710k |
| lead + specialist + reviewer | `deepseek-v4-pro` | 127.0M | 1.66M |

Builder/scout (the mechanical work) are on flash, which is 4.4× cheaper per
miss token and 3.3× cheaper per output token than pro. There is no measured
instance of pro doing mechanical edits.

### 4.3 The loaded-skill surface is re-sent every call

The two skills preloaded into every worker — `github` and `hermes-agent` — are
2,729 B and 16,125 B of `SKILL.md` respectively (measured on disk), ≈ **4.7k
tokens**, re-sent on all 2,374 calls ≈ **11.2M cached tokens, ~5 % of the
cached volume**. `AGENTS.md` adds ~690 tokens. These are hub skills (routing
tables pointing at on-demand references), so most of that 5 % is not even
instructions that fire on a given card.

## 5. Ranked interventions (measured only)

Only interventions with a measured effect appear here; anything unmeasured is
in §6. "Reduces" names which line it cuts — **fresh**, **cached**, or **output**.

| # | Intervention | Reduces | Measured effect | Est. saving | Confidence |
|---|---|---|---|---|---|
| 1 | Fix the infra blockers behind blocked/spawn-failed runs | fresh + cached | 24 % of runs (23/94) end non-completed; 3 cards = 796 respawn-guards, all infra (token, data mount, duplicate twin) | up to ~24 % of the spawn floor; ≤ ~$2 of the cached line | high (counts measured; $ estimate derived) |
| 2 | Trim the loaded skill surface (hub skills → on-demand refs) | cached | 18.9 KB ≈ 4.7k tokens/call × 2,374 = 11.2M cached (5 % of cached) | ≤ ~5 % of the cached line (~$0.15) | high (size measured; load behaviour assumed) |
| 3 | Cap context growth per card (compaction / history window) | cached | tail context 150k–190k vs 91k average; M3 156k/call vs M4 95k/call | bounds the tail; unquantified without host logs | medium (mechanism known, current settings unread) |

The honest bottom line of the table: **every measurable intervention is worth
single-digit dollars, because the whole M2–M4 bill is ~$10 off-peak.** The
value of #1 and #2 is *latency* — a blocked run and a fat skill both make every
call in a session slower — not money. #1 is also the only one that is free to
fix (it is configuration/hygiene, not a code change).

## 6. Hypotheses — not measured, deliberately excluded from §5

Per the task contract, these cannot be ranked until they are measured; each
names the exact host command that would measure it. All four need the per-call
`agent.log`, which lives on the host and is not mounted in the worker sandbox
(the sandbox has the board DB and the repo, not `~/.hermes/profiles/*/logs`).

- **Tool-output discipline** (`cat` of whole files, full test dumps) — would
  reduce *cached* (and *fresh* when re-read). The mechanism is real but the
  magnitude is unmeasured: it needs the context jump per call, correlated with
  tool calls. *Measure:* add per-call `read_file`/`terminal` size to the log
  join, or eyeball the three most expensive cards' `in=` growth in `agent.log`.
- **Delegation** (`delegate_task` isolated context) — would reduce *cached* on
  the parent (and *fresh* overall). Which M2–M4 cards would have been cheaper
  delegated is unmeasured. *Measure:* compare per-card `in=` against the parent
  that would have paid only a summary.
- **Fixed cost at call #1** — the absolute size of the spawn floor. *Measure:*
  `grep 'API call #1' <profile>/logs/agent.log` and read `in=` on the first call
  of a card's session.
- **Effective compaction/history-window settings** — the operator's config is
  not readable from the sandbox. *Measure:* `hermes config get` for the
  history/compaction keys, then compare against the observed tail growth.

## 7. The one change shipped this round

The measurement itself now reproduces: [`scripts/token_cost_report.py`](../../scripts/token_cost_report.py)
parses the per-call `cache=` field and reports `cached`/`fresh` in the `--json`
output (total, by-milestone, by-profile, by-model, per-card) and in the text
summary. Before, the `CACHE` regex was defined but never used, so the split
could not be produced by anyone but the operator; after, it is one command.

- **Before/after, same script:** before — `--json` reported only `in=`/`out=`/
  `calls` (the 91:1 number). After — `--json` adds `cached` and `fresh`, and the
  text header prints `input processed … (cached … = 97.3%, fresh …)` and
  `fresh:output = 2.43:1`.
- **Verified:** `python3 -m pytest tests/unit/test_token_cost_report.py -q` —
  3 passed (synthetic log lines + synthetic DB; the cache/fresh split is checked
  against a hand-computed answer). Full suite `python3 -m pytest tests -m "not realgame" -q` — 353 passed, 9 deselected.

No Hermes internals, no config change, no game bytes, no merge.

## 8. Reproduce

```bash
python3 scripts/token_cost_report.py --board retrolab --json
```

Runs on the **host** (the script joins the board DB against each profile's
`logs/agent.log`; the worker sandbox does not mount those logs, so there it
reports `cards_measured: 0` against the live DB). The operator's cache-aware
run on this board produced the §1 split: 221,747,051 processed / 215,817,088
cached / 5,929,963 fresh / 2,437,509 out. The synthetic test in §7 is the
sandbox-side proof that the parser computes the same split correctly.

## 9. Recommendation

Do **not** chase the 91:1. The money is ~$10 off-peak, of which output (the
well-predicted "work produced") is the largest share and cached input is ~$3.
If the goal is a *faster* board rather than a cheaper one, fix the infra
blockers (§4.1) — 24 % of spawns currently die on missing credentials or data —
and then, once the host log is available, measure the §6 hypotheses rather than
guessing.
