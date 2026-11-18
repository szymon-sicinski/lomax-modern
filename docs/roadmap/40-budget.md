# 40. Budget

Token and cost estimates for milestones M0…M11 and releases v0.2…v1.0. This
document exists so the human can decide *whether* to start a milestone, not just
*whether* it is technically feasible. Companion documents:
[`10-milestones.md`](10-milestones.md), [`20-releases.md`](20-releases.md).

> **Revision v2** (LMX-9/M2, 2026-11-18). Re-costed for the **disc-less /
> own-engine** decision (open decision #4, resolved). The old v1 table priced the
> *disc-owner ddraw proxy*; that row is gone and the spine is re-cut
> (data layer → engine core → presenter → input → audio → packaging, plus the
> surviving tooling). **The own engine is not a shim**: at *expected* it is
> ~1.5× the old ~$8–9 natural-mix figure, and the engine-core milestone carries a
> band wide enough to push the whole plan toward ~3× if scope explodes (§5).
>
> **Revision v3** (2026-11-18). Reconciled with the measured M2–M4 run. The board
> database records **wall-clock and card/review counts but not token counts**, so
> the estimate-vs-measured table in [Revision](#revision) reports tokens as *not
> recorded* rather than inventing a number, and re-forecasts M5/M6 from measured
> per-card wall-clock.

## Table of contents

1. [Units and rates](#1-units-and-rates)
2. [Method](#2-method)
3. [Assumptions](#3-assumptions)
4. [Per-milestone estimate (low / expected / high)](#4-per-milestone-estimate-low--expected--high)
5. [Cumulative by release](#5-cumulative-by-release)
6. [Spend reporting (no ceiling)](#6-spend-reporting-no-ceiling)
7. [What this cannot estimate](#7-what-this-cannot-estimate)
8. [Revision](#revision)

---

## 1. Units and rates

**Tokens first, money second.** Every milestone is estimated as *input tokens*
and *output tokens* (separate), then converted to money at two model rates.

Rates are derived by least-squares from the measured calibration in each
profile's `state.db` `session_model_usage`, cross-checked against the reference
per-session costs. Derived rates, per **1 M tokens**:

| Model | input | output | note |
|---|---|---|---|
| `deepseek-v4-pro` | ~$0.45 | ~$3.40 | lead / specialist / reviewer |
| `deepseek-flash` | ~$0.09 | ~$1.28 | scout / builder |

A specialist investigation at these rates (≈79k in / 36k out) costs ≈ $0.15, a
scout investigation (≈62k in / 40k out) ≈ $0.06, a lead roadmap session
(≈95k in / 82k out) ≈ $0.32.

**Peak vs off-peak.** Peak is 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri, and is
**2×** the off-peak price. The whole plan assumes off-peak execution.

## 2. Method

1. **Decompose** each milestone into work items, each tagged to a profile whose
   measured cost anchors it.
2. **Anchor** each work item to the calibration / reference points:

   | Work item | profile (model) | in | out |
   |---|---|---|---|
   | planning / roadmap authoring | lead (pro) | 60k–95k | 40k–82k |
   | research investigation | specialist (pro) | 79k | 36k |
   | research investigation | scout (flash) | 62k | 40k |
   | implementation card | specialist (pro) | 100k | 55k |
   | implementation card | builder (flash) | 55k | 21k |
   | review pass | reviewer (pro) | 40k | 35k |

3. **Apply rework.** The *expected* scenario multiplies the clean-run total by a
   per-milestone rework factor; *low* is the clean run; *high* is the top of the
   rework band. The engine core (M3) is new, unfamiliar territory and gets the
   widest band.
   - trivially verifiable (M0, M6, M10): **1.1×** expected, 1.25× high
   - normal build work (M1, M5, M7, M11): **1.5×** expected, 2.0× high
   - hard / unfamiliar (M2, M3, M4, M8, M9): **2.0×** expected, 3.0× high
4. **Convert** to cost at both model rates (off-peak); peak is 2×.

## 3. Assumptions

- **Model mix** follows the routing table: scout/builder on `deepseek-flash`;
  lead/specialist/reviewer on `deepseek-v4-pro`. The own-engine plan is *more*
  specialist-heavy than v1 (the engine core, `ANIM`/`NMY` probing and the
  renderer are specialist work), which shifts the natural mix toward `@pro`.
- **Context per card.** ~25 % of each session's tokens re-read repo context.
- **Review cycles.** One reviewer pass per implementation card, plus rework.
- **Cost driver.** Output tokens dominate (~3–15× the input rate).
- **Off-peak.** All numbers are off-peak; peak doubles them.

## 4. Per-milestone estimate (low / expected / high)

"in/out" are thousands of tokens. Costs are the **expected** (reworked) scenario
at each model rate, off-peak.

| Milestone | rework | low in/out | exp in/out | high in/out | $ @pro | $ @flash |
|---|---|---|---|---|---|---|
| M0 roadmap (incurred) | — | 175k / 152k | 175k / 152k | 175k / 152k | $0.60 | $0.21 |
| M1 platform & patching strategy (incurred) | 1.5× | 320k / 187k | 480k / 280k | 640k / 374k | $1.18 | $0.40 |
| M2 data-layer completeness | 2.0× | 480k / 260k | 960k / 520k | 1,440k / 780k | $2.20 | $0.75 |
| M3 engine core | 2.0× | 900k / 510k | 1,800k / 1,020k | 2,700k / 1,530k | $4.28 | $1.47 |
| M4 presenter (own renderer) | 2.0× | 420k / 240k | 840k / 480k | 1,260k / 720k | $2.01 | $0.69 |
| M5 controller & input | 1.5× | 280k / 160k | 420k / 240k | 560k / 320k | $1.01 | $0.35 |
| M6 audio (SFX + music path) | 1.1× | 90k / 50k | 100k / 55k | 110k / 60k | $0.23 | $0.08 |
| M7 packaging | 1.5× | 160k / 90k | 240k / 135k | 320k / 180k | $0.57 | $0.19 |
| M8 asset pipeline (upscaler + pack) | 2.0× | 307k / 173k | 614k / 346k | 921k / 519k | $1.47 | $0.49 |
| M9 2× internal-render spike | 2.0× | 559k / 326k | 1,118k / 652k | 1,677k / 978k | $2.74 | $0.93 |
| M10 password tool | 1.1× | 95k / 56k | 105k / 62k | 119k / 70k | $0.26 | $0.09 |
| M11 level editor + translation | 1.5× | 462k / 249k | 693k / 374k | 924k / 498k | $1.60 | $0.54 |
| v1.0 integration & QA | 1.25× | 250k / 152k | 312k / 190k | 375k / 228k | $0.79 | $0.27 |

**Why M3 is the widest and biggest row.** The engine core (map/collision/
entities/timing, tick-for-tick) is the one thing the old plan deliberately
avoided; it is the *only* genuinely unfamiliar milestone, so it carries the
2.0×/3.0× rework band and dominates the cumulative. If "engine scope explosion"
(`30-risks.md` P1) fires, the **high** (or beyond) applies and the whole plan
moves toward ~3×.

## 5. Cumulative by release

Cumulative **expected** spend. Tokens in thousands; cost off-peak.

| Release | Milestones | cum input | cum output | cum $ @pro | cum $ @flash |
|---|---|---|---|---|---|
| v0.2 | M0 | 175k | 152k | $0.60 | $0.21 |
| v0.3 | M0–M1 | 655k | 432k | $1.78 | $0.61 |
| v0.4 | +M2 | 1,615k | 952k | $3.98 | $1.36 |
| v0.5 | +M3 | 3,415k | 1,972k | $8.26 | $2.83 |
| v0.6 | +M4 | 4,255k | 2,452k | $10.27 | $3.52 |
| v0.7 | +M5+M6 | 4,775k | 2,747k | $11.51 | $3.95 |
| v0.8 | +M7 | 5,015k | 2,882k | $12.08 | $4.14 |
| v0.9 | +M8 | 5,629k | 3,228k | $13.55 | $4.63 |
| v0.10 | +M9 | 6,747k | 3,880k | $16.29 | $5.56 |
| v0.11 | +M10+M11 | 7,545k | 4,316k | $18.15 | $6.19 |
| v1.0 | +integration | 7,857k | 4,506k | $18.94 | $6.46 |

**The multiplier, stated plainly.** The old (shim) plan ended at 5,879k in /
3,398k out — roughly **$8–9 natural-mix** by v1.0. The own-engine plan ends at
7,857k in / 4,506k out — **~$13 natural-mix** by v1.0 (between the $18.94 `@pro`
and $6.46 `@flash` columns, weighted toward `@pro` because the engine core is
specialist work). That is **~1.5× at expected**, ~1.2× at low (the engine core
goes smoothly), and **~3× at high** (engine scope explosion). Confidence in the
dollar figure is **low** — see §7.

## 6. Spend reporting (no ceiling)

The human set **no budget ceiling**; the plan tracks actual spend and reports it,
and the human decides when it stops being worth it.

- **Per milestone.** The milestone's worker records actual input/output tokens
  (from the profile `state.db` `session_model_usage`) in a `kanban_comment` at
  completion, against the low/expected/high band in §4, so drift is visible
  milestone by milestone rather than discovered at the end.
- **Soft tripwire (informational only).** If a milestone's *actual* input-token
  spend exceeds **2× its high estimate** before its exit criteria are met, the
  worker flags it in a comment — a prompt for the human to review
  value-for-effort, **not** an automatic stop.

Per-milestone 2×-high reference points (input tokens): M1 1,280k · M2 2,880k ·
M3 5,400k · M4 2,520k · M5 1,120k · M6 220k · M7 640k · M8 1,842k ·
M9 3,354k · M10 238k · M11 1,848k · v1.0 750k. M9's kill criterion is
functional, not financial: "more than viewport + tile + sprite + fade" means
stop and publish findings.

## 7. What this cannot estimate

- **The engine core is unfamiliar territory.** M3's numbers are anchored to the
  same card/review model as the rest, but a tick-for-tick reimplementation has
  no measured precedent in this repo; the token model under-states the *variance*
  even though the band is already the widest. Treat the $4.28 `@pro` M3 row as
  order-of-magnitude.
- **Playtest and human-judgement loops.** "No shimmer", "recognisable sheets",
  "feels right" are human verdicts; the rework factor is a crude proxy.
- **The 2× spike is a probability, not a price.** M9 may be abandoned early
  (cheap) or soak the full band.
- **The disc-owner appendix is unpriced.** The `ddraw.dll` proxy is optional; if
  the human later wants it for disc owners, it is a separate, unestimated track.
- **Model price changes.** Rates are anchored to today's measured
  `session_model_usage`; a provider repricing moves every dollar number while
  leaving token numbers intact.
- **The `default` profile's 41 flash sessions** skew a naive blended flash rate;
  the rates here come from a least-squares fit over all six calibration rows.

## Revision

**v3 — reconcile with the measured M2–M4 cost (2026-11-18).** The M2–M4 vertical
slice has run, so §4's estimates can be checked against the board instead of
intuition. The check surfaced two corrections: **(1)** the board database
records **wall-clock and card/review counts**, not token counts — so the
token-axis comparison below is *not recorded*, not zero; and **(2)** on the axis
that *is* measured, the dominant variance is rework, and it is concentrated in
M4.

### Estimate vs measured, per milestone

§4's expected-scenario token figures are shown for reference; the measured
column is wall-clock, because token spend for M2–M4 was never recorded on the
board (see [Source query](#source-query)).

| Milestone | §4 exp in/out | measured tokens | measured wall-clock | cards | review verdicts |
|---|---|---|---|---|---|
| M2 data layer | 960k / 520k | not recorded | 83.5 min | 12 | 4 approve / 3 changes |
| M3 engine core | 1,800k / 1,020k | not recorded | 41.9 min | 4 | 1 / 1 |
| M4 presenter | 840k / 480k | not recorded | 131.3 min | 20 | 6 / 5 |
| M7 packaging | 240k / 135k | not recorded | 12.1 min | 2 | 1 / 0 |
| research & M0–M1 (incurred) | — | not recorded | 184.7 min (+15 wasted runs) | 28 | 6 / 4 |

"Cards" counts distinct cards with at least one completed run; "wall-clock" sums
completed runs' `ended_at − started_at`. Card ids per milestone are in
[Card inventory](#card-inventory); the query that reproduces the table is in
[Source query](#source-query). Verdict counts sum the approve/changes columns;
two reviewer cards ended without a verdict and are excluded — `t_3eee5fb9` (M4,
obsolete: PR #14 merged while the review ran) and `t_19a527f3` (research, moot:
PR already merged).

### Drivers of the variance

The single largest driver was one bit-replication bug: the 6-bit green channel
was widened with `(g << 2) | (g >> 2)` instead of `(g << 2) | (g >> 4)`, and
because the same formula lived in three modules (`engine/render.py`,
`renderer.py`, `presenter.py`) it forced changes-required re-reviews of PRs #21,
#22, #23 and #25 before the fix (t_63fa35db, t_2c68fd71, t_42448bbe). M4's
integration did not save review cost: the five leaf PRs (#21 renderer, #22
present CLI, #23 conformance, #24 runbook, #25 green fix) were each reviewed
independently — several with changes-required, two rebased (t_740f5aa0,
t_bea18a7b) — and then the synthesis card (t_9d241cef) assembled them into one
integration PR #26 that received two further reviews before merge, leaving M4
with 20 cards of which 12 were reviewer cards (11 returned a verdict; `t_3eee5fb9`
ended obsolete — see the table footnote). The 22 non-completed runs are a
board-wide total, not a research-phase one: 15 sit on the 28 listed research /
M0–M1 cards, 6 on the two archived cards (`t_9ede11a8` ×5, `t_07060d2e` ×1), and
1 on the M4 review card `t_3eee5fb9`. Their causes, as the board records them,
are environment and process failures rather than research waste — a `/workspace`
permission error (`t_ef9f28da`), a worktree path outside any git repo and an
unsupported `deepseek-pro` model name (`t_c6963f52`), missing GitHub push
credentials and PAT scopes (`t_9ede11a8`, `t_1be13ca0`), duplicate or superseded
cards (`t_9ede11a8`, `t_07060d2e`, `t_cb2f724c`), a PR merged while its review
ran (`t_3eee5fb9`), and a force-pushed history undercutting a branch
(`t_86bd51ab`). These are real wall-clock but sit mostly in M0/M1, which §4 marks
"incurred" without capturing that waste.

### Re-forecast for M5/M6

Measured per-card wall-clock (completed runs) is the only per-card cost the
board records, so it replaces the per-milestone guess; token spend stays
unmeasurable from the board (not recorded).

| profile | measured wall-clock per card (M2–M4) |
|---|---|
| specialist (implementation) | ~13–25 min (n=3) |
| builder (implementation) | ~7.7–13.3 min (n=4 substantive) |
| reviewer (one pass) | ~5.5–7.5 min (central; n=20, range 3.1–10.0) |
| lead (synthesis) | ~14.9 min (n=1) |
| lead (merge) | ~1.8–2.0 min (n=2) |

Bands are the completed-run minutes (`ended_at − started_at`, per the
[Source query](#source-query)) of the cards each profile performed. The
implementation bands exclude cards that measured wall-clock without doing
implementation work: **builder** excludes the three rebase cards (`t_4bbddac9`
0.0, `t_740f5aa0` 2.3, `t_bea18a7b` 2.8) and the one-line green fix
(`t_63fa35db` 1.8), leaving the four substantive cards (`t_a1835193` 7.7,
`t_e78bf2b9` 11.2, `t_60957323` 11.4, `t_6aeaa5c4` 13.3); **specialist**
excludes the re-scoped WLD-reader card `t_d7e61628` (9.9, work already shipped
as LMX-5/PR #6), leaving `t_c06b9a88` 13.3, `t_9b2ba6ab` 20.5, `t_64c84629`
24.9; **lead** splits synthesis (`t_9d241cef` 14.9) from the two merges
(`t_c0e87352` 1.8, `t_d225eaaf` 2.0). The reviewer band is the central cluster
of the 20 verdict-returning passes, not the measured maximum (`t_42448bbe` 10.0,
`t_2a861d65` 8.9).

- **M5 controller & input** (§4: 420k / 240k exp). Decomposed as ~3 specialist
  implementation cards + ~3 review passes + 1 lead synthesis, the measured rates
  give **~1.2–1.9 h wall-clock across ~7 cards** (3×13–25 + 3×5.5–7.5 + ~15
  min).
- **M6 audio** (§4: 100k / 55k exp). ~1 specialist implementation card + 1
  review pass gives **~0.3–0.5 h wall-clock across 2 cards** (13–25 + 5.5–7.5
  min).

**Does the integration approach change the forecast?** Yes, and not in the
direction §4 assumed. The "one review instead of five" only materialised in M4
*after* the five leaf PRs had already been reviewed and rebased, so the measured
review load was the sum of the leaves plus the integration — roughly double the
method's one-pass-per-card assumption. A milestone that integrates first and
reviews the merged result once would approach the single-pass assumption; a
milestone that reviews leaves first pays the M4 pattern. Until the process
changes, treat §4's rework factors (2.0× for M2–M4, 1.5× for M5) as consistent
with — or slightly optimistic against — the measured changes-required rate of
41.9% (13 changes / 31 verdicts; 40.0–50.0% across the M2, M3, M4 and research
rows, 0 of 1 for M7).

### Card inventory

- **M2 (12):** t_d7e61628, t_9b2ba6ab, t_6aeaa5c4, t_c0e87352, t_1293fd33,
  t_1365e154, t_6b6601f3, t_67905c08, t_41cbde19, t_4fd0f0ab, t_5f092437,
  t_4bbddac9.
- **M3 (4):** t_64c84629, t_63fa35db, t_7afb3f54, t_42448bbe.
- **M4 (20):** t_c06b9a88, t_e78bf2b9, t_60957323, t_a1835193, t_9d241cef,
  t_d225eaaf, t_740f5aa0, t_bea18a7b, t_3eee5fb9, t_d3f62935, t_14d7744f,
  t_2c68fd71, t_233d2248, t_317b4d3c, t_ee91cc6d, t_fd036ee5, t_2a861d65,
  t_77c54196, t_46009157, t_e190f112.
- **M7 (2):** t_b25db0cf, t_c2b4c84a.
- **research & M0–M1 (28):** t_ef9f28da, t_813193a6, t_c6963f52, t_abee9ea7,
  t_c465a167, t_dce28ab7, t_9a019c4a, t_d5b45ed5, t_1be13ca0, t_f46072b8,
  t_a8a3e64a, t_a2860e97, t_1025ab57, t_50f8aa85, t_1c414fa8, t_a37f3f36,
  t_3493cb71, t_10e0211f, t_a206a709, t_37c2b249, t_cb2f724c, t_beed4320,
  t_484c8080, t_da891848, t_0b888f1d, t_86bd51ab, t_19a527f3, t_bdfecee7.

### Source query

Measured from the retrolab board database
(`/home/nwah/.hermes/kanban/boards/retrolab/kanban.db`). Wall-clock = sum of
`task_runs.ended_at − task_runs.started_at` over rows with `outcome='completed'`;
milestone assigned from the card title (`LMX-10 M2/M3/M4/M7` tags; review /
rebase / merge cards keyed by PR number). The per-run query:

```sql
SELECT task_id, profile,
       (ended_at - started_at) / 60.0 AS wall_clock_min
  FROM task_runs
 WHERE outcome = 'completed'
   AND ended_at IS NOT NULL;
```

Milestone and profile-bucket assignment is applied from the [card
inventory](#card-inventory) above (title tags, and review/rebase/merge cards
keyed by PR number), since the board has no milestone column. **Tokens are not
in this database**: a run's token count would be recovered by joining the
`session_id` recorded in its `owner_admitted` event to the `session_model_usage`
table of the profile's `state.db`
(`/home/nwah/.hermes/profiles/<profile>/state.db`), a separate database that was
not mounted in the worker environment — hence "not recorded" above.
