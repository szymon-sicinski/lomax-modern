# 40. Budget

Token and cost estimates for milestones M0…M8 and releases v0.2…v1.0. This
document exists so the human can decide *whether* to start a milestone, not just
*whether* it is technically feasible. Companion documents:
[`10-milestones.md`](10-milestones.md), [`20-releases.md`](20-releases.md).

## Table of contents

1. [Units and rates](#1-units-and-rates)
2. [Method](#2-method)
3. [Assumptions](#3-assumptions)
4. [Per-milestone estimate (low / expected / high)](#4-per-milestone-estimate-low--expected--high)
5. [Cumulative by release](#5-cumulative-by-release)
6. [Burn-rate control](#6-burn-rate-control)
7. [What this cannot estimate](#7-what-this-cannot-estimate)

---

## 1. Units and rates

**Tokens first, money second.** Every milestone is estimated as *input tokens*
and *output tokens* (separate), then converted to money at two model rates.

Rates are derived by least-squares from the measured calibration in each
profile's `state.db` `session_model_usage` (input tokens, output tokens, cost),
cross-checked against the reference per-session costs. Derived rates, per
**1 M tokens**:

| Model | input | output | note |
|---|---|---|---|
| `deepseek-v4-pro` | ~$0.45 | ~$3.40 | lead / specialist / reviewer |
| `deepseek-flash` | ~$0.09 | ~$1.28 | scout / builder |

A specialist investigation at these rates (≈79k in / 36k out) costs ≈ $0.15, a
scout investigation (≈62k in / 40k out) ≈ $0.06, a lead roadmap session
(≈95k in / 82k out) ≈ $0.32 — all inside the cited reference ranges, which is
the cross-check.

**Peak vs off-peak.** Peak is 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri, and is
**2×** the off-peak price. The whole plan assumes off-peak execution; multiply
any cost below by 2 for a peak run.

## 2. Method

1. **Decompose** each milestone into work items, each tagged to a profile whose
   measured cost anchors it (see the anchor table below).
2. **Anchor** each work item to the calibration / reference points rather than
   inventing a per-task average. The per-item token anchors used here:

   | Work item | profile (model) | in | out |
   |---|---|---|---|
   | planning / roadmap authoring | lead (pro) | 60k–95k | 40k–82k |
   | research investigation | specialist (pro) | 79k | 36k |
   | research investigation | scout (flash) | 62k | 40k |
   | implementation card | specialist (pro) | 100k | 55k |
   | implementation card | builder (flash) | 55k | 21k |
   | review pass | reviewer (pro) | 40k | 35k |

3. **Apply rework.** Rework is not optional: this project has already burned two
   blocked attempts and one rejected completion on a single README card. The
   *expected* scenario multiplies the clean-run total by a per-milestone rework
   factor; *low* is the clean run; *high* is the top of the rework band.
   - trivially verifiable (M0, M5): **1.1×** expected, 1.25× high
   - normal build work (M1, M3, M4, M8): **1.5×** expected, 2.0× high
   - hard / unfamiliar (M2, M6, M7): **2.0×** expected, 3.0× high
4. **Convert** to cost at both model rates (off-peak); peak is 2×.

## 3. Assumptions

- **Model mix** follows the routing table: scout/builder run on
  `deepseek-flash`; lead/specialist/reviewer run on `deepseek-v4-pro`. This is
  why the "@flash vs @pro" spread matters — it is the routing table, priced.
- **Context per card.** Each session re-reads the repo's research docs and the
  card body before doing new work; the token anchors are *total* session tokens,
  of which roughly **25 % is re-reading repo context** and 75 % is new work.
- **Review cycles.** One reviewer pass per implementation card, plus the rework
  factor for the implementer. Reviewers are never the implementer.
- **Cost driver.** Output tokens dominate cost (~3–15× the input rate), so a
  milestone's cost scales with how much it *writes* (a verbose spike report or
  a large PR body costs more than a tight one).
- **Off-peak.** All numbers below are off-peak; peak doubles them.

## 4. Per-milestone estimate (low / expected / high)

"in/out" are thousands of tokens. Costs are the **expected** (reworked) scenario
at each model rate, off-peak.

| Milestone | rework | low in/out | exp in/out | high in/out | $ @pro | $ @flash |
|---|---|---|---|---|---|---|
| M0 roadmap (incurred) | — | 175k / 152k | 175k / 152k | 175k / 152k | $0.60 | $0.21 |
| M1 platform & patching strategy | 1.5× | 320k / 187k | 480k / 280k | 640k / 374k | $1.18 | $0.40 |
| M2 open-source presenter | 2.0× | 609k / 348k | 1,218k / 696k | 1,827k / 1,044k | $2.94 | $0.99 |
| M3 controller & input | 1.5× | 414k / 237k | 621k / 356k | 828k / 474k | $1.50 | $0.51 |
| M4 `.WLD` toolkit + exporter | 1.5× | 362k / 194k | 543k / 291k | 724k / 388k | $1.24 | $0.42 |
| M5 password tool | 1.1× | 95k / 56k | 105k / 62k | 119k / 70k | $0.26 | $0.09 |
| M6 asset pipeline (upscaler + pack) | 2.0× | 307k / 173k | 614k / 346k | 921k / 519k | $1.47 | $0.49 |
| M7 2× internal-render spike | 2.0× | 559k / 326k | 1,118k / 652k | 1,677k / 978k | $2.74 | $0.93 |
| M8 level editor + translation | 1.5× | 462k / 249k | 693k / 374k | 924k / 498k | $1.60 | $0.54 |
| v1.0 integration & QA | 1.25× | 250k / 152k | 312k / 190k | 375k / 228k | $0.79 | $0.27 |

**Why the ranges are wide where they are.** M2 and M7 get a 2.0×/3.0× band
because they touch the binary (DLL shim under Wine, and the execute-buffer/width
patching) — unfamiliar, failure-prone territory. M6 gets it because art quality
is subjective and the go/no-go loop is a playtest loop, not a test suite. M5 is
narrow (1.1×) because a password codec is trivially verifiable by a round-trip
test. M0 is shown as *incurred*, not estimated — it already happened.

## 5. Cumulative by release

Cumulative **expected** spend, so the human can see what v0.3 costs before v0.1
exists. Tokens in thousands; cost off-peak.

| Release | cum input | cum output | cum $ @pro | cum $ @flash |
|---|---|---|---|---|
| v0.2 | 175k | 152k | $0.60 | $0.21 |
| v0.3 | 655k | 432k | $1.78 | $0.61 |
| v0.4 | 1,873k | 1,128k | $4.72 | $1.60 |
| v0.5 | 2,494k | 1,484k | $6.22 | $2.11 |
| v0.6 | 3,037k | 1,775k | $7.47 | $2.53 |
| v0.7 | 3,142k | 1,837k | $7.73 | $2.62 |
| v0.8 | 3,756k | 2,183k | $9.19 | $3.11 |
| v0.9 | 4,874k | 2,835k | $11.93 | $4.04 |
| v0.10 | 5,566k | 3,208k | $13.53 | $4.58 |
| v1.0 | 5,879k | 3,398k | $14.32 | $4.85 |

The **natural mix** (flash for scout/builder, pro for lead/specialist/reviewer)
lands between the two columns — roughly **$8–9 cumulative by v1.0**. The gap
between the @flash and @pro columns *is* the routing table: putting scout and
builder work on flash instead of pro is a 3× saving, so the routing table is a
cost decision as much as a competence decision.

## 6. Burn-rate control

Each milestone has the same stop trigger, surfaced the same way:

- **Trigger.** If a milestone's *actual* spend (input tokens, tracked in the
  profile `state.db`) exceeds **2× its high estimate** before its exit criteria
  are met, stop and re-plan.
- **Event that surfaces it.** The milestone's worker calls
  `kanban_comment` (spend-to-date vs. the 2×-high line) and
  `kanban_block(kind="needs_input")` with the re-plan question, rather than
  silently continuing.

Per-milestone 2×-high ceilings (input tokens): M1 1,280k · M2 3,654k ·
M3 1,656k · M4 1,448k · M5 238k · M6 1,842k · M7 3,354k · M8 1,848k ·
v1.0 750k. M7's ceiling is advisory only: its *functional* kill criterion
("needs more than viewport + tile + sprite + fade patching") fires first.

## 7. What this cannot estimate

- **The M2 target-host fork is unpriced.** The M2 row assumes the *disc-owner*
  ddraw proxy (12–20 agent-days, `10-milestones.md`). If the human selects the
  own-engine path for disc-less users instead, M2 becomes a materially larger,
  unpriced milestone and every cumulative figure from v0.4 onward shifts — the
  tables above must be re-costed before v0.4 is committed, not silently reused.
- **Playtest and human-judgement loops.** "No shimmer", "no halo", "recognisable
  sheets" are human verdicts; the rework factor is a crude proxy, not a count.
- **Wine/Proton version churn.** A future Wine regression or a new Proton
  release can invalidate M2/M3 assumptions regardless of spend; the estimate
  assumes the compat matrix in M1 stays representative.
- **The M7 spike is a probability, not a price.** It may be abandoned early
  (cheap) or soak the full band; the "expected" figure assumes it is attempted
  to completion once.
- **Model price changes.** Rates are anchored to today's measured
  `session_model_usage`; a provider repricing moves every dollar number while
  leaving the token numbers intact — which is why tokens, not dollars, are the
  unit of record.
- **The `default` profile's 41 flash sessions** skew a naive blended flash rate;
  the rates here come from a least-squares fit over all six calibration rows,
  not from dividing one profile's total.
