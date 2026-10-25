# Demo video and submission

## The video (target 1:55, hard limit under 2:00)

Judges may stop at 2:00 and may judge from the video alone, so every second has to show something working. Record from the **deployed Azure URL** with the address bar visible at least once. VJ records the voiceover himself, in his own words. No music, or a track whose free commercial licence is logged in `docs/ASSET_LICENSES.md`.

The shape: open on the problem, prove it in the first 35 seconds, show the part nobody else will have (the verifier, and killing an agent), then the real footage, then close on the line. About 270 spoken words in total. If a take runs long, cut words, never the shots.

| Time | On screen | Voiceover | Caption burned in |
|---|---|---|---|
| 0:00–0:08 | Broadcast view, match running. An overlay slides in over the play. | "Millions of people watch the same match and get the same broadcast. A tactics nerd and a first-timer see exactly the same thing." | Same match. |
| 0:08–0:18 | Pull back to the Control Room: events ticking in, latency readout. | "This is Novessa Pitchside. A made-up league plays a full match live. No real club, no real player. Stats hit the screen in under 150 milliseconds." | Fully synthetic data. Under 150 ms. |
| 0:18–0:34 | A pressure shift. Instant tags first (pass difficulty, speed), then the "why" card lands. Cut to the Verifier line showing the numbers it checked. | "Then the why. A producer agent picks the moment. An analyst explains it. A verifier recomputes every number before it airs. If a claim fails, you get the plain figures instead." | Nothing airs unchecked. |
| 0:34–0:54 | **Split view**, same moment: Analyst in English, a casual fan in Spanish with the voice playing. | "Same moment, two viewers. The analyst sees the pressing lines and the numbers behind them. This fan is new to football, so they get the story, in Spanish, out loud." | Your story. |
| 0:54–1:06 | Player focus on one player, then one-number mode switching the overlay layer. | "Follow one player all match. Or pick the single number you care about, and the whole screen reorganises around it." | One player. One number. |
| 1:06–1:26 | **Real footage**: players tracked and tagged by team, a sprint speed appears, scrub the clock, end on the scorecard. Dataset credit visible. | "It's not only synthetic. This is a real amateur match from an open dataset. Same idea, detected straight from video: players tracked, speeds measured, scored against the dataset's own labels. Players are strong. The ball is the weak spot, and we say so." | Real footage, CC BY 4.0. Players found 71%. Position error about 1 m. |
| 1:26–1:44 | Control Room: agent graph lighting up, then the **chaos switch** kills the Analyst. The graph shows the fallback and the broadcast keeps running. | "Behind it, a team of agents on Microsoft Agent Framework and Foundry. Watch. I kill the analyst mid-match. The rest carry on, and every claim leaves an audit trail." | Kill an agent. Nothing breaks. |
| 1:44–1:52 | Recap page in Arabic, then the A2A call returning a recap. | "At full time, recaps in six languages, for any viewer, and for other agents over A2A." | 6 languages. A2A. |
| 1:52–1:58 | Wordmark over the broadcast. Live URL, repo URL, one line of services. | "Novessa Pitchside. Same match. Your story." | Live on Azure. 150 viewers, 0 errors. All Bicep. |

### Why this order

- **Problem in eight seconds.** The first thing a judge hears is the reason the project exists.
- **Proof before explanation.** The overlay and the "why" card are on screen before we name a single technology.
- **The verifier is the idea.** "Nothing airs unchecked" is the line the rubric rewards under agentic design, and it is true: models never compute a number.
- **Failure on camera.** Killing an agent is what the multi-agent category checks for. Do it live, do not describe it.
- **Honesty is a strength.** Saying the ball is the weak spot makes the 71% believable.

### Before you record

1. Warm the cache so no model call is slow on camera: `uv run python -m scripts.warm_overlay_text`, then `scripts.push_cache`.
2. Confirm two API replicas are up and the live URL answers from a logged-out window.
3. Pick the pressure moment and the goal you will cut to during rehearsal. Note the match minute for each so every take lands the same shot.
4. Check the Verifier line you show is a real one from that moment, not a made-up example.
5. Browser at 1920×1080, 60 fps, zoom 125% so overlays read on a laptop. Hide bookmarks and other tabs.
6. Do the chaos switch once in rehearsal and note how long recovery takes. Cut to the recovered state, never fake it.
7. Read the script aloud with a timer. Under 1:55 spoken, or cut words.

### Edit

Cut every pause. Burn in the captions from the table (many judges watch muted). Zoom into overlays in the edit. No music. Upload to YouTube as **public**, not unlisted.

## Project pitch (hackathon page)

**Novessa Pitchside. Same match. Your story.**

Millions of people watch the same match and get the same broadcast, whether they live for pressing stats or just want to know why their team looks rattled. Novessa Pitchside gives each viewer their own version of the game, live, in their own language.

A synthetic engine plays a full 90 minutes in a fictional league. A deterministic stats layer turns it into momentum, control and chaos, pressure and pass difficulty, and puts instant overlays on screen in under 150 ms. A newsroom of agents built with Microsoft Agent Framework on Microsoft Foundry does the rest. A producer picks the moments, an analyst explains why they matter, and a verifier recomputes every number before it airs. A model never calculates anything. If a claim fails, the viewer gets the plain numbers. Other agents write for each viewer, translate and voice it in six languages, recap the match, and answer questions without spoiling the minute you are on. Kill any agent mid-match and the broadcast carries on.

The output is a timed overlay protocol any graphics engine could render. Analysts, casual fans, first-timers and audio-description users each get a different picture and different words, built around their club, their player or the one number they care about. We also pointed the same idea at a real amateur match from an open dataset (SoccerTrack v2, CC BY 4.0). It tracks players and measures speeds from video, scored against the dataset's own labels.

It runs on Azure with a live link, scaled and load-tested with 150 viewers and no errors, and every resource is Bicep.

**Built with:** Microsoft Foundry, Microsoft Agent Framework, A2A, our own MCP server, Azure MCP, Azure Container Apps, Azure Static Web Apps, Azure Event Hubs, Azure Cosmos DB, Azure Blob Storage, Azure AI Translator, Azure AI Speech, Azure AI Content Safety, Azure Monitor and Application Insights, Azure Load Testing, Key Vault, Bicep and the Azure Developer CLI, GitHub Actions and GitHub CLI.

_(Keep this under about 300 words. VJ rewrites anything that doesn't sound like him.)_

## Submission checklist (do it from a logged-out browser on Tue 27)

- [ ] Video under 2:00, public on YouTube, URL on the project page
- [ ] **Repo public** (rules §4.4: required for the entry to count), README renders, licence present, no secrets, no footage files
- [ ] Live URL loads with no login in under 3 seconds; testing instructions on the page
- [ ] Pitch names the Microsoft and Azure tech
- [ ] Project linked to the challenge
- [ ] Team members listed on the submission, with no personal data in the text
- [ ] Budget alert active, uptime test active, API min replicas set until 10 Nov
