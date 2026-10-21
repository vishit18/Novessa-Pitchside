# The agent system

This is 20% of the score directly (Agentic Design) and the whole basis of the **Best Multi-Agent System** category prize. The judges for that prize check four things, so the design is built around them:

1. Specialised agents with **distinct roles**
2. Coordination through **shared state** and **clean handoffs**
3. **Recovery from failure**
4. An end-to-end result a **single agent couldn't match**

Build with **Microsoft Agent Framework (Python)** using its graph-based **Workflow** API, with Foundry as the model provider (`FoundryChatClient` or the current equivalent; check Microsoft Learn MCP for the latest API before writing code, it changes often). Every agent run is traced to Foundry / App Insights.

## The newsroom metaphor

Think of it as a live TV gallery. The state engine is the data team. The agents are the editorial staff.

```
 candidate moments + state snapshot
            │
            ▼
   ┌─────────────────┐   drops / merges / ranks, decides airtime
   │  PRODUCER       │──────────────────────────────────────────┐
   └────────┬────────┘                                          │
            │ brief: "explain this, 2 lines, priority high"      │
            ▼                                                   │
   ┌─────────────────┐  claims + evidence   ┌─────────────────┐ │
   │  ANALYST        │ ───────────────────▶ │  VERIFIER       │ │
   │  (the "why")    │ ◀─── rejection +     │  (proves every  │ │
   └─────────────────┘      reason, 1 retry │  claim via MCP) │ │
                                            └────────┬────────┘ │
                                    verified insight │          │
            ┌────────────────────────────────────────┤          │
            ▼                                        ▼          │
   ┌─────────────────┐                     ┌─────────────────┐  │
   │  NARRATOR       │ persona variants    │  STORY KEEPER   │  │
   │  (analyst/casual│                     │  (running arcs, │  │
   │  /kids/a11y)    │                     │  milestones)    │  │
   └────────┬────────┘                     └─────────────────┘  │
            ▼                                                   │
   ┌─────────────────┐   ┌─────────────────┐                    │
   │  LOCALISER      │──▶│  VOICE          │  (Azure AI Speech) │
   │  (Translator +  │   │  commentary     │                    │
   │  LLM polish)    │   └─────────────────┘                    │
   └────────┬────────┘                                          │
            ▼                                                   ▼
      Overlay Gateway  ◀──── overlay instructions (timed) ── PRODUCER

   RECAP EDITOR (half-time / full-time), exposed over A2A
   QA (Content Safety) sits on every text output before it airs
```

## Agents

### 1. Producer (orchestrator)
- **Role:** the editorial brain. Decides *what* goes on screen, *when*, for *how long*, and what gets dropped. A real broadcast can't show 40 graphics a minute. This is the agent most other entries won't have.
- **Inputs:** candidate moments with significance scores, what's currently on screen, recent airtime log, match context.
- **Outputs:** `ProducerDecision` — for each moment: `air | merge_with | hold | drop`, priority, target personas, overlay slot (lower third, side panel, full-screen replay card), duration, and a brief for the Analyst.
- **Rules it follows:** max one language overlay on screen at a time per slot; never interrupt a goal sequence; boost favourite-club and favourite-player moments in the persona layer, not globally.
- Model: `chat-fast`. Falls back to a deterministic ranking policy if the model times out.

### 2. Tactical Analyst
- **Role:** explains *why* the moment matters in football terms: control vs chaos, pressure shifts, rhythm, individual quality, game state.
- **Must** output structured claims with evidence references, e.g. `{"claim": "Kestrel have won the ball back 4 times in Ashford's half in 5 minutes", "evidence": {"metric":"pressure_index","window":"20:00-25:00","value":...}}`.
- **Tools (via our MCP server):** `get_state`, `get_player_stats`, `get_window_stats`, `compare_periods`, `get_pass_network`.
- Model: `chat-strong`.

### 3. Verifier
- **Role:** proves every claim before it airs. Re-queries the numbers through the MCP tools independently and checks each claim. Returns `approved | rejected(reason) | corrected(new_claim)`.
- On rejection, the Analyst gets one retry with the reason. Second failure → the Producer airs the deterministic fallback card (numbers only, no prose) or drops it.
- Logs the verification trail; the Control Room shows a green tick / red cross per claim. Judges love seeing this happen live.
- **Story check** (`backend/agents/story.py`, 21 Oct): numbers can all be right while the sentence is wrong ("Kestrel Bay has a clear chance" on Ashford's penalty; a 27th-minute goal "just before half-time"). For goals, penalties, big chances and cards the headline may not credit only the other club, and time phrases ("before half-time", "stoppage time", "early", "late") must fit the clock. Runs in the Verifier (Analyst gets one retry with the reason), on every Narrator variant (falls back to the verified analysis text) and on recaps (one retry). `scripts/check_story.py` screens the warmed cache.
- Note: about 30 other entries mention fact-checking, so this alone isn't our differentiator. It's the hygiene that makes the Producer, personas, voice and real footage trustworthy.

### 4. Narrator
- **Role:** turns a verified insight into persona variants:
  - **Analyst:** numbers-forward, terminology allowed, ≤ 2 lines
  - **Casual:** story-first, no jargon, one number max
  - **Kids / first match:** explains the rule or idea in plain words
  - **Accessibility:** written for audio description, describes what happened spatially
- Also writes the short live commentary line for the Voice agent.

### 5. Story Keeper
- **Role:** keeps the running narrative state across the match: active storylines, milestones, player arcs ("Okafor's quiet first half"), callbacks ("that's the third time this has happened"). Writes to shared state; the Narrator and Recap Editor read from it.
- Runs every ~5 match-minutes and on major moments.

### 6. Localiser
- **Role:** multi-language. Uses **Azure AI Translator** for the raw translation, then a light LLM pass to fix football terminology and tone per language (e.g. proper local football idiom). Languages: EN, ES, FR, AR, HI (PT optional).
- Caches every output.

### 7. Voice
- **Role:** turns commentary lines into speech with **Azure AI Speech** neural voices per language. Short, punchy, timed to the moment. Streamed to the client as audio.

### 8. Recap Editor
- **Role:** half-time and full-time recaps per persona and language, plus a 60-second highlights script and "what did I miss?" catch-ups for viewers who join late.
- **Exposed over A2A** so an external broadcaster agent could ask "give me the full-time recap for match m01 in Spanish, casual tone". Include a tiny demo client script that calls it. Only a handful of entries mention A2A/MCP in their pitch, so this is a real differentiator.
- Model: `chat-strong`.

### 9. Scout and Ask the Analyst (viewer questions)
- **Role:** a viewer types a question mid-match ("why are Kestrel struggling?", "how fast has Wragg been?", in any language). The **Scout** (`chat-fast`) picks up to three lookups from a fixed list (match state, a player, a team's last N minutes, then versus now, leaders, key moments) or declines anything not about this match. Code runs the lookups on `MatchIntel`, **clipped to the viewer's own clock**, so an answer can never spoil what is still to come. The **Analyst** (`chat-strong`) answers from those rows only, in the viewer's persona; the **Verifier** checks every number in the answer against the rows (one retry, then a numbers-only answer); the **Localiser** puts it in the viewer's language; the safety gate checks both question and answer. Cached per (seed, question, 30 s of match time, persona, language).
- **Failure paths:** Scout down → rules (the players named in the question, plus the match state). Analyst down → numbers-only answer. Off-topic or unsafe → declined, with no lookups.
- **Voice questions:** hold the mic in the Ask panel and speak. The gateway sends the clip to Azure AI Speech fast transcription (keyless, Entra token, same resource as the voices) with the viewer's locale and a phrase list of the match's names, so "Wragg" comes back as Wragg. The words land in the question box and go through the same Scout, Analyst, Verifier, Localiser path. No model is asked to hear anything; the question text is what gets checked. Speech down or not configured → the mic is hidden and typing still works.
- Code: `backend/agents/ask.py`, prompts `scout.md` and `ask.md`, endpoint `POST /matches/{id}/ask`, UI `frontend/src/components/AskSheet.tsx` (Ask button or `/` on the broadcast, Ask on the phone view).

### QA gate (not an agent, a step)
Every text output passes **Azure AI Content Safety** before it airs. Failures get logged and replaced with the fallback card.

## Shared state

A `MatchContext` object (in-memory per match, snapshotted to Cosmos DB) that all agents read and write through typed methods:
- current state snapshot (from the state engine)
- moment queue and decisions
- verified insights
- storylines and milestones
- airtime log
- per-agent health (latency, failures, circuit-breaker status)

Agents don't pass huge prompts to each other; they pass IDs and read the shared context. That's the "handoff through shared state" the judges want to see.

## Failure recovery (design it, then demo it)

| Failure | Recovery |
|---|---|
| Model timeout (> 3 s) | retry once with backoff, then fallback output |
| Model 429 / quota | circuit breaker opens for that agent; Producer switches to deterministic mode; Control Room shows it |
| Verifier rejects claim | Analyst retries once with reason; then numbers-only card |
| Translator fails | fall back to LLM translation; then English with a "translation unavailable" flag |
| Speech fails | text-only commentary, no audio; the Ask panel hides the mic |
| Content Safety flags | drop text, log, show fallback card |
| Agent process crash | workflow checkpointing (Agent Framework supports it) resumes from last checkpoint |

Add a **chaos switch** in the Control Room: "kill the Analyst for 30 seconds". In the demo we flip it and the viewer sees the system degrade gracefully and recover. This directly answers the judges' "recover from failures" check.

## Proving multi-agent beats single-agent

`scripts/eval_single_vs_multi.py`: run the same 3 matches with (a) one big prompt agent and (b) our workflow. Measure with **Foundry evaluations** (groundedness, relevance, fluency) plus our own: % claims verified, hallucinated numbers, latency, cost per match, overlay spam rate. Put the table in the README and flash it for 3 seconds in the video.

## Our MCP server (`backend/mcp_server/`)

"Match Intelligence MCP": exposes the state engine as tools: `get_state`, `get_player_stats`, `get_window_stats`, `compare_periods`, `get_pass_network`, `list_moments`, `get_recap`. The Analyst and Verifier call it, and anything else MCP-compatible can too (VS Code Copilot, Claude, a broadcaster's tools). Show it working from VS Code in the README. This hits the rubric's "MCP integration" line directly.

## How it is built (21 Oct)

- `backend/agents/workflow.py`: the Agent Framework `WorkflowBuilder` graph. Executors: Producer, Analyst, Verifier, Narrator, Gate. The Verifier has an edge back to the Analyst (one retry with the reason) and an edge to the Gate for the numbers-only fallback card. Messages are small Pydantic models (`models.py`); everything else lives in `MatchContext`.
- `intel.py` (`MatchIntel`) is the one source of numbers. The MCP server (`backend/mcp_server/server.py`) wraps it, and the Verifier calls `measure` to recompute each claim.
- The Analyst never calculates. It gets an **evidence menu** (computed rows for the moment: state, 5-minute windows per team, involved players) and copies rows into its claims. The Verifier re-measures every claim and also rejects any number in the prose that no claim, engine fact, clock reading or window backs. No model is involved in verifying.
- The Narrator may not add numbers either; if it does, the verified Analyst text airs instead.
- `llm.py` (`ResilientLLM`): timeout, one retry with backoff, JSON validated against the Pydantic model, circuit breaker, OpenTelemetry span, per-agent health, chaos `kill`. A failure raises `AgentUnavailable` and each agent uses its fallback.
- Cache: `cache.py`, keyed `(seed, moment_id, stage, persona, lang)`. Only verified results are cached. Local runs write `data/cache/agents/`; if that is not writable the temp dir is used.
- Gateway: `AgentRuntime` runs batches of five candidate moments (significance 50 or more) in the background and each socket attaches the text with `op: "update"` once it is ready. Chaos switch: `POST /agents/{agent}/kill?seconds=30`. Health: `GET /agents/health`. Trails: `GET /matches/{id}/insights`.
- Story Keeper (`storykeeper.py`): rule-based storylines from state (lead, dominance, pressing, bookings, ten men, chaos). The text has no digits on purpose. The Narrator may call back to a storyline; the Recap Editor reads them.
- Localiser (`localiser.py`): Azure AI Translator (keyless, v3 on the resource's own domain) then a model polish for football wording. After each step numbers and names are compared with the English; a change means that step is thrown away. Fallback order: translator + polish, translator only, model only, English with `translation: unavailable`. Languages: en, es, fr, ar, hi, pt.
- Voice (`voice.py`): Azure AI Speech neural voices (MP3), made on first request and cached on disk. `GET /matches/{id}/audio/{moment_id}?persona=&lang=`. The update overlay carries `audio_url`. If Speech is down there is simply no audio.
- Recap Editor (`recap.py`): a fact sheet is computed in code, the model writes the prose, every number must appear in the fact sheet (retry once, then a plain template). `GET /matches/{id}/recap?kind=half_time|full_time&persona=&lang=`.
- A2A (`backend/a2a/server.py`): agent card at `/.well-known/agent-card.json`, JSON-RPC at `/a2a/jsonrpc`, skill `match_recap`. Requests are plain text ("full-time recap for derby_01 in Spanish, casual tone"), parsed by rules. Demo client: `uv run python -m scripts.a2a_client <base url> "<ask>"`.

## Prompts

Store each agent's system prompt in `backend/agents/prompts/<agent>.md`, versioned. Keep them short and specific. Every agent uses JSON-schema structured output. Tone rules for all text: sound like a sharp, warm football broadcaster; no clichés like "a game of two halves" unless the data actually shows it; never invent a number.
