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

## Table of contents

1. [Units and rates](#1-units-and-rates)
2. [Method](#2-method)
3. [Assumptions](#3-assumptions)
4. [Per-milestone estimate (low / expected / high)](#4-per-milestone-estimate-low--expected--high)
5. [Cumulative by release](#5-cumulative-by-release)
6. [Spend reporting (no ceiling)](#6-spend-reporting-no-ceiling)
7. [What this cannot estimate](#7-what-this-cannot-estimate)

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
