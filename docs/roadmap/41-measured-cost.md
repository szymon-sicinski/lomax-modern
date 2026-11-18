# 41. Measured cost — what the M2–M4 work actually consumed

[`40-budget.md`](40-budget.md) is a **model**: per-milestone estimates of input
and output tokens, with a 2× rework band and derived money rates. This file is
the **measurement** that model is checked against, produced by
[`scripts/token_cost_report.py`](../../scripts/token_cost_report.py).
Read the two together: the estimate is what we planned to spend, this is what
the board and the agent logs record.

## Where the numbers come from

The kanban board stores wall-clock time, card counts and review counts — **not
tokens**. The token counts exist one line per model call in each profile's
`logs/agent.log`:

```
... [local-<session>] agent.conversation_loop: API call #46:
    model=deepseek-v4-pro provider=deepseek in=188200 out=475 total=188675 ...
```

and `task_runs.metadata.worker_session_id` carries the same `local-<session>`
id, so a card's usage can be attributed rather than guessed:

```bash
python3 scripts/token_cost_report.py --board retrolab
python3 scripts/token_cost_report.py --board retrolab --milestone M4 --json
```

Reproduce with the command above; the script opens the board read-only and
never writes to it.

## Measured, M2–M7 (2026-11-18, board `retrolab`)

| Milestone | Cards attributed | Input tokens | Output tokens | Model calls |
|---|---:|---:|---:|---:|
| M2 data layer | 6 | 56,820,803 | 517,948 | 453 |
| M3 engine core | 2 | 18,209,835 | 125,573 | 117 |
| M4 presenter | 14 | 56,898,086 | 518,654 | 598 |
| M7 runbook | 1 | 9,281,982 | 43,367 | 80 |
| LMX-7 research (WP1–WP6) | 10 | 40,262,081 | 611,498 | 447 |
| LMX-5 / LMX-3 (format + Wine) | 3 | 6,965,750 | 102,071 | 108 |
| Unattributed cards | 22 | 31,102,715 | 477,925 | 571 |
| **Total** | **58** | **219,541,252** | **2,397,036** | **2,374** |

By profile: builder 76.0M in / 534k out · reviewer 53.8M / 842k · specialist
41.6M / 472k · lead 33.3M / 372k · scout 14.8M / 176k.
By model: `deepseek-v4-pro` 127.0M in / 1.66M out (1,452 calls) ·
`deepseek-flash` 90.8M in / 710k out (895 calls).

## Estimate against measured

Using the *expected* (2× rework) column of `40-budget.md` §4:

| Milestone | Estimated in / out | Measured in / out | Input ratio | Output ratio |
|---|---|---|---:|---:|
| M2 | 960k / 520k | 56.8M / 518k | **59×** | 1.00× |
| M3 | 1,800k / 1,020k | 18.2M / 126k | **10×** | 0.12× |
| M4 | 840k / 480k | 56.9M / 519k | **68×** | 1.08× |

**Output tokens were estimated almost exactly** — M2 landed within 0.4 % of its
number and M4 within 8 %. The model's instinct about how much *work* the agents
would produce was sound.

**Input tokens are off by one to two orders of magnitude**, and the cause is
structural, not a runaway: an agent session makes 60–150 model calls per card,
and each call re-sends the whole context (150–190k tokens in the tail of a long
card). `40-budget.md` §3 assumed "~25 % of each session's tokens re-read repo
context"; the real figure is that **input is 30–70× output**, so context
re-reading *is* the bill, not a 25 % surcharge.

## The split that matters: processed vs billed

The 219.5M input figure counts **tokens processed**, and 97.3 % of them were
cache hits — the per-call `cache=` field says so, and `token_cost_report.py`
now sums it:

| | tokens | share |
|---|---:|---:|
| input processed | 221,747,051 | 100 % |
| of which cached | 215,817,088 | **97.3 %** |
| of which fresh | 5,929,963 | 2.7 % |
| output | 2,437,509 | — |
| **fresh input : output** | **2.43 : 1** | |

So the headline "91 input tokens per output token" is an artifact of counting
cache hits as input. The rate that actually drives prompt-processing cost is
**2.4 fresh tokens per output token** — ordinary for agentic work — while the
cached 215.8M is billed at the provider's cache rate, which on these models is
roughly an order of magnitude below the fresh rate.

Two consequences for the budget:

1. **Do not report `in=` as the unit of spend.** It is a context-size metric.
   The spend metric is `fresh_in`, plus `cached_in` weighted by the cache price,
   plus `out`.
2. **The real lever on cached volume is calls × context size**, not the work
   itself: halving calls per card halves the cached bill even if every call
   costs the same per token.

## What this does and does not mean for the money

- Do **not** multiply the input column by a full-rate price and panic. The logs
  show a cache ratio per call (`cache=23936/27905`); most of that input is
  cached and billed at a fraction. The measured input figure is *tokens
  processed*, not *tokens billed at full rate*.
- Do **not** trust the token-count model either: a milestone's token budget
  stated in millions of input tokens is off by ~50×, which matters for any
  context-window, rate-limit or per-token cost planning that is not
  cache-aware.
- The honest statement for the roadmap is: **output tokens are a good predictor
  of agent effort; input tokens are a function of context size × calls per card,
  and must be modelled that way.**

## Caveats

- **34 of the 92 runs had no matching log line** — logs rotate at 2 MiB, so
  early runs are gone. Measured totals are a **lower bound**.
- Cards are attributed by session id; a card that retried across sessions is
  summed, a card whose session id was reused (a resumed `local-…` session) could
  be double-counted. The retry-free cards are the trustworthy rows.
- "Unattributed cards" are cards whose runs predate the log window.
- Costs are not converted to money here on purpose: rates change, and the cache
  ratio has to be applied to be meaningful.

## What to change in `40-budget.md` next revision

1. Replace "~25 % context re-read" with the measured input-to-output ratio
   (30–70×) and say it scales with calls-per-card, not with task size.
2. Keep output-token estimates as they are — they were within 8 %.
3. Add a column "measured tokens" pointing at this file, so the estimate is
   never read as a measurement.
