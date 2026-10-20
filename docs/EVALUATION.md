# Single agent against the newsroom

`scripts/eval_single_vs_multi.py` takes the 47 moments the newsroom chose to air across derby_01, derby_02, derby_03, and writes each one two ways with the same computed evidence: by one prompt (the single agent, whose answer airs as it is) and by the full workflow (Producer, Analyst, Verifier, Narrator, Gate). The first rows use a deterministic check: every number in the text must match a computed fact for that moment. The Foundry rows are Microsoft Foundry evaluators (`azure-ai-evaluation`), run by `chat-fast`, a different model from the one that wrote the text.

| | Single agent | Newsroom |
|---|---|---|
| Moments with a number that is not a computed fact | **1 of 47 (2.1%)** | **0 of 47 (0.0%)** |
| Unsupported numbers in total | 1 | 0 |
| Time | 1.7 s per moment (median) | 28.8 s for a batch of 5 moments, in parallel |
| Claims the Verifier sent back | none (no Verifier) | 8 moments |
| Aired as a numbers-only card | none | 0 moments |
| Texts the Foundry judge scored | 47 of 47 | 47 of 47 |
| Foundry groundedness (1 to 5, higher is better) | 5.0 | 4.68 |
| Foundry relevance (1 to 5, higher is better) | 4.72 | 3.68 |
| Foundry fluency (1 to 5, higher is better) | 3.6 | 3.34 |

## Reading it

**Numbers.** The single agent, given the same evidence menu, put a number that is not a computed fact into 1 of 47 moments. The newsroom put none into 47. A single well-fed prompt is mostly honest about numbers, so what the Verifier adds is a guarantee, not a large correction. It did send a claim back in 8 of 47 moments: errors in the Analyst step that an unchecked pipeline would have aired.

**Quality.** On Foundry's evaluators the single agent scored higher on groundedness, relevance, fluency. The newsroom writes to a tighter format (a headline of six words, a trimmed body, no number the Analyst did not claim) and the evaluators favour fuller text. We have not closed that gap, and we do not claim the newsroom writes better.

**Speed.** The single agent took 1.7 s per moment. The newsroom took 28.8 s for a batch of 5, running in parallel, because it makes three model calls and a deterministic check. On the broadcast the instant overlay is already on screen, so this delays the explanation, never the picture.

**What the newsroom is for.** The single prompt wrote one casual line. The newsroom writes four viewer types in six languages from one verified analysis, keeps an audit trail for every moment (what each agent said, what the Verifier rejected), falls back to a numbers-only card instead of airing something unchecked, and keeps the broadcast running when an agent is slow or down. Those are the reasons for the structure, rather than better prose.

## Examples of what the single agent got wrong

- `mom-derby_02-0051`: "Saltmarsh Turn Up The Heat. At 69', Saltmarsh are pressing way harder than two minutes ago (pressure index 90), forcing more ball wins and disrupting Millwater’s midfield — could flip momentum in the final 20. " (not backed by the data: 20)

## What this does and does not show

- The number check is blunt. It asks whether a number appears among the computed facts for the moment. It cannot see a true number attached to the wrong team or metric, which the Verifier does catch because it recomputes each claim as a (metric, team, window) triple.
- The newsroom's text is checked by the same kind of code that judges it, so a zero there is expected by construction.
- The Foundry evaluators are language models. They are not a ground truth, and they reward longer, fuller text. The newsroom writes to a tight format on purpose.
- The comparison uses one prompt for the single agent, written by us. A better prompt might score higher still.
- Three matches, one run each. Which moments the Producer airs can differ between runs. Re-run it with `uv run --group eval python -m scripts.eval_single_vs_multi`.
