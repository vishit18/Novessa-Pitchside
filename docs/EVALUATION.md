# Single agent against the newsroom

`scripts/eval_single_vs_multi.py` takes the 41 moments the newsroom chose to air across derby_01, derby_02, derby_03, and writes each one two ways with the same computed evidence: by one prompt (the single agent, whose answer airs as it is) and by the full workflow (Producer, Analyst, Verifier, Narrator, Gate). The first rows use a deterministic check: every number in the text must match a computed fact for that moment. The Foundry rows are Microsoft Foundry evaluators (`azure-ai-evaluation`), run by `chat-fast`, a different model from the one that wrote the text.

| | Single agent | Newsroom |
|---|---|---|
| Moments with a number that is not a computed fact | **3 of 41 (7.3%)** | **0 of 41 (0.0%)** |
| Unsupported numbers in total | 3 | 0 |
| Moments with a story error (wrong club, wrong time, result called mid-match, code names, a booking said to change tactics) | **10 of 41 (24.4%)** | **0 of 41 (0.0%)** |
| Time | 1.6 s per moment (median) | 27.5 s for a batch of 5 moments, in parallel |
| Claims the Verifier sent back | none (no Verifier) | 12 moments |
| Aired as a numbers-only card | none | 0 moments |
| Texts the Foundry judge scored | 41 of 41 | 41 of 41 |
| Foundry groundedness (1 to 5, higher is better) | 5.0 | 4.56 |
| Foundry relevance (1 to 5, higher is better) | 4.85 | 3.66 |
| Foundry fluency (1 to 5, higher is better) | 3.76 | 3.22 |

## Reading it

**Numbers.** The single agent, given the same evidence menu, put a number that is not a computed fact into 3 of 41 moments. The newsroom put none into 41. A single well-fed prompt is mostly honest about numbers, so what the Verifier adds is a guarantee, not a large correction. It did send a claim back in 12 of 41 moments: errors in the Analyst step that an unchecked pipeline would have aired.

**Story.** Numbers can all be right while the sentence is wrong. The same story rules the Verifier applies found an error in 10 of 41 single-agent texts and 0 of 41 newsroom texts: crediting the wrong club, a time phrase that does not fit the clock, a result called before full time, a metric's code name pasted into prose. No model judges this; it is the same code that runs on every line before it airs.

**Quality.** On Foundry's evaluators the single agent scored higher on groundedness, relevance, fluency. The newsroom writes to a tighter format (a headline of six words, a trimmed body, no number the Analyst did not claim) and the evaluators favour fuller text. We have not closed that gap, and we do not claim the newsroom writes better.

**Speed.** The single agent took 1.6 s per moment. The newsroom took 27.5 s for a batch of 5, running in parallel, because it makes three model calls and a deterministic check. On the broadcast the instant overlay is already on screen, so this delays the explanation, never the picture.

**What the newsroom is for.** The single prompt wrote one casual line. The newsroom writes four viewer types in six languages from one verified analysis, keeps an audit trail for every moment (what each agent said, what the Verifier rejected), falls back to a numbers-only card instead of airing something unchecked, and keeps the broadcast running when an agent is slow or down. Those are the reasons for the structure, rather than better prose.

## Examples of what the single agent got wrong

- `mom-derby_01-0011`: "Penalty to Ashford Rovers. Viggo Falkman was brought down in the box and Tobias Wragg steps up from 12 yards — a huge chance to break the deadlock and swing momentum Ashford’s way with the game still 0-0." (not backed by the data: 12)
- `mom-derby_02-0051`: "Saltmarsh Turn Up The Heat. Saltmarsh City have cranked their press — 24 pressure events in five minutes and a pressure index of 77.8 — disrupting Millwater’s previously dominant possession. That intensity could force turnovers and swing momentum in the final 22 minutes." (not backed by the data: 22)
- `mom-derby_02-0053`: "Saltmarsh Seizes the Initiative. In the last two minutes Saltmarsh City has pushed momentum their way — more possession (51.1%), crisper passing (78% accuracy) and increased pressure — they’re controlling the game as we head into the final 18 minutes." (not backed by the data: 18)
- `mom-derby_01-0003`: "Balogun Booked — Ashford Caution. Tunde Balogun shown a yellow at 05:31 for a late challenge; Ashford are desperate to disrupt Kestrel’s heavy possession (81.7% last 5) but need better control after just 10 passes and 50% accuracy." (a booking is about the player; do not say it changed the team's tactics)
- `mom-derby_01-0016`: "Orbaiz Cautioned — Ashford Hold Lead. Lucho Orbaiz booked at 31:51 for a foul, slowing Kestrel Bay’s momentum. The yellow matters because Ashford’s control (60% possession last 5) keeps them on top while Kestrel Bay struggles to create chances." (a booking is about the player; do not say it changed the team's tactics)
- `mom-derby_01-0037`: "Penalty to Seal It?. 77:17 — Tobias Wragg steps up after Viggo Falkman was fouled in the box. Ashford, leading 1-0 and riding heavy pressure (pressure index 85.7), can put the game to bed with this spot kick." (Viggo Falkman committed the foul; he was not fouled)
- `mom-derby_02-0017`: "Ekstrand’s Needle Threaded. At 27:33 Lasse Ekstrand completed a 96-rated difficult pass to keep Millwater probing — his 80% match accuracy and composed distribution help sustain Millwater’s 58% possession spell and build real pressure." (say what the numbers show, not how anyone feels)
- `mom-derby_02-0018`: "Hedlund Booked — Saltmarsh Caution. Yellow to Ove Hedlund at 28:36 for a late challenge; Saltmarsh lose a key defender’s composure while Millwater control 62% possession recently, tipping momentum away." (a booking is about the player; do not say it changed the team's tactics; say what the numbers show, not how anyone feels)

## What this does and does not show

- The number check is blunt. It asks whether a number appears among the computed facts for the moment. It cannot see a true number attached to the wrong team or metric, which the Verifier does catch because it recomputes each claim as a (metric, team, window) triple.
- The newsroom's text is checked by the same kind of code that judges it, so a zero there is expected by construction. That holds for the story check too: what it shows is how often one prompt alone would have aired those mistakes, not that the newsroom writers never make them (the Verifier sent 12 back).
- The Foundry evaluators are language models. They are not a ground truth, and they reward longer, fuller text. The newsroom writes to a tight format on purpose.
- The comparison uses one prompt for the single agent, written by us. A better prompt might score higher still.
- Three matches, one run each. Which moments the Producer airs can differ between runs. Re-run it with `uv run --group eval python -m scripts.eval_single_vs_multi`.
