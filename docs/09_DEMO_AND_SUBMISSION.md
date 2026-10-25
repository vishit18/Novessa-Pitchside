# Demo video and submission

## The video (target 1:55, hard limit under 2:00)

Judges may stop at 2:00 and may judge from the video alone, so every second has to show something working. Record from the **deployed Azure URL** with the address bar visible at least once. VJ records the voiceover himself, in his own words. No music, or a track whose free commercial licence is logged in `docs/ASSET_LICENSES.md`.

The shape: open on the problem, prove it in the first 35 seconds, show the part nobody else will have (the verifier, and killing an agent), then the real footage, then close on the line. About 270 spoken words. If a take runs long, cut words, never the shots.

Everything below uses the demo match **`derby_01`: Ashford Rovers v Kestrel Bay, finishing 2-1**. It is the best prepared match: its agent text is verified and cached, and Spanish, Hindi and Arabic versions of the key moments are already in the cache. Minutes are match clock. Drag the timeline to a minute, or use `?t=` (seconds) on Split and Control.

### The match, scene by scene

| Clock | What happens | Why we use it |
|---|---|---|
| 02:00 | Ashford lift the press (pressure shift, 3 of 3 claims proven) | The "why" card. Cached in English, Spanish, Hindi, Arabic. |
| 05:31 | Yellow card, Ashford | The trail shows the narrator being rejected once for saying a booking changed the tactics. |
| 26:33 / 26:47 | Penalty to Ashford, then the goal, 1-0 | The biggest moment of the first half. Instant tags first, then the "why". Cached in Spanish. Split view starts here. |
| 45:07 | Tazi's high-difficulty pass | Pass difficulty and player context. Cached in Spanish. |
| 71:45 | Red card, Ashford down to ten | Cached in English. |
| 77:17 | Penalty to Ashford. The Verifier **rejects the first draft** ("use club names, never their codes") and passes the second | The Control Room shot. This is a real, recorded rejection. |
| 77:31 | Penalty saved, momentum swings | Cached in English. |
| 84:01 / 85:09 | Goal 2-0, then Kestrel Bay pull one back | Full-time recap material. |

### The cut

| Time | Where to be | What to do | Voiceover | Caption burned in |
|---|---|---|---|---|
| 0:00-0:08 | `/watch?match=derby_01&speed=4`. Drag the timeline to about 26:20. | Let the penalty and goal play. The name tag and shot-speed overlay appear instantly. | "Millions of people watch the same match and get the same broadcast. A tactics nerd and a first-timer see exactly the same thing." | Same match. |
| 0:08-0:18 | `/control?match=derby_01` | Scroll so the gauges and the overlay feed are in shot. Point at the latency numbers. | "This is Novessa Pitchside. A made-up league plays a full match live. No real club, no real player. Stats hit the screen in under 150 milliseconds." | Fully synthetic data. Under 150 ms. |
| 0:18-0:34 | `/watch?match=derby_01`. Drag to about 01:50 and let it run past 02:00. | The instant overlay lands, and a moment later the "Ashford lift the pressure" card arrives. Cut to the Control Room moment queue for that moment, with "verifier: 3/3 claims proven" in the trail. | "Then the why. A producer agent picks the moment. An analyst explains it. A verifier recomputes every number before it airs. If a claim fails, you get the plain figures instead." | Nothing airs unchecked. |
| 0:34-0:54 | `/split?match=derby_01` (it opens about 40 s before the first goal). Left: Analyst, English. Right: First match, Spanish, voice on. | Play through the 26:47 goal. Left shows pressing halos and evidence chips. Right shows the big direction arrow, no shirt numbers, and Spanish text and voice. | "Same moment, two viewers. The analyst sees the pressing lines and the numbers behind them. This fan is new to football, so they get the story, in Spanish, out loud." | Your story. |
| 0:54-1:06 | `/watch?match=derby_01`, drag to about 45:00 | Player focus on Zakaria Tazi: the camera follows, and the card shows his rank among forwards. Then pick "Just one number", sprint speed. | "Follow one player all match. Or pick the single number you care about, and the whole screen reorganises around it." | One player. One number. |
| 1:06-1:26 | `/real` | Play, let a sprint speed appear, scrub the clock once, end on the scorecard (players found 71%, position error about 1 m). Keep the SoccerTrack v2 credit in shot. | "It's not only synthetic. This is a real amateur match from an open dataset. Same idea, detected straight from video: players tracked, speeds measured, scored against the dataset's own labels. Players are strong. The ball is the weak spot, and we say so." | Real footage, CC BY 4.0. Players found 71%. |
| 1:26-1:44 | `/control?match=derby_01&t=4640` (77:20) | Open the 77:17 moment: first draft rejected for using club codes, second proven. Then press the chaos switch on the Analyst plate, go to the broadcast and ask a **new** question (see "What to expect"). | "Behind it, a team of agents on Microsoft Agent Framework and Foundry. The verifier caught this one and sent it back. Now I kill the analyst mid-match. The rest carry on, and every claim leaves an audit trail." | Kill an agent. Nothing breaks. |
| 1:44-1:52 | `/recap?match=derby_01&kind=full_time&persona=analyst&lang=ar`, then the A2A call in a terminal | Show the Arabic recap right to left, then the terminal returning a recap. | "At full time, recaps in six languages, for any viewer, and for other agents over A2A." | 6 languages. A2A. |
| 1:52-1:58 | Wordmark over the broadcast | Live URL and repo URL on screen. | "Novessa Pitchside. Same match. Your story." | Live on Azure. 150 viewers, 0 errors. All Bicep. |

The A2A call, ready to paste (the deployed Recap Editor):

```bash
uv run python -m scripts.a2a_client https://ca-a2a-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io "Full-time recap for derby_01 in Arabic"
```

Run it once before recording and check it answers. If it is slow, record the terminal separately and cut it in.

### What to expect, and what to do if it does not happen

- **Instant overlays** (name tag, shot speed, pass difficulty) arrive with no model call. If one is missing, the page is not connected: hard refresh and start the scene again.
- **The "why" card** comes after the instant overlay. For every moment in the table it is served from the cache, so it should land in under a second. If it takes 4 s or more, the cache is cold: see "Warm everything".
- **Split view in Spanish.** Rely on the 26:47 goal and the 45:07 pass. Other moments may arrive in English if they were never translated.
- **The Verifier rejection.** Only 77:17 is a recorded Verifier rejection on this match ("use club names, never their codes", then 3 of 3 proven). 05:31 and 26:33 show the *narrator* being rejected, which is also fine on screen but is a different line in the trail. Open 77:17.
- **The chaos switch.** It switches an agent off for 30 seconds. A cached moment never calls the model, so killing the Analyst while cached moments replay changes the plate to "Switched off" but changes nothing on the broadcast. To show recovery that means something: switch the Analyst off, then press `/` on the broadcast and ask a question nobody has asked before. That runs the live path. Expect the answer to fall back to plain computed numbers instead of a written sentence, and the broadcast to keep playing. This is how the code is built, not something I have watched happen, so rehearse it once, note exactly what you see, and cut to what really happens.
- **Arabic recap.** For `derby_01` only the English recaps and a Hindi casual full-time recap are cached. The Arabic one is not, so it calls the model on first open (a few seconds). Warm it first.

## Warm everything (the day before, and again right before recording)

A cold model call on camera is a dead second, so there are three layers of warm.

1. **The cache that ships in the repo.** `data/cache/agents/seed_43.json` is `derby_01`. It holds 18 verified moments, Spanish, Hindi and Arabic versions of some of them, the English recaps for all four personas, the overlay translation tables for Spanish, French, Arabic, Hindi and Portuguese, and four Ask answers. Nothing to run, it is committed.
2. **Copy it to Cosmos, because the live site reads from Cosmos, not from the repo.** After any change to the local cache:
   ```bash
   az login
   uv run python -m scripts.push_cache
   ```
   It prints `N entries in pitchside/agent_cache`. Safe to repeat.
3. **Warm what is missing by doing it once on the live site.** Anything not cached is written to Cosmos the first time it runs, so the second run is instant. Open each of these once, on the live URL, and wait for it to finish:
   - `/recap?match=derby_01&kind=full_time&persona=analyst&lang=ar` (the Arabic recap in the script)
   - `/split?match=derby_01`, play through the 26:47 goal with the right pane on First match and Spanish, and switch the voice on once so the Spanish audio is generated
   - `/watch?match=derby_01`, one run from about 01:50 to 02:30 as Analyst, English
   - `/control?match=derby_01`, press **Start the agents** if it says "Start", so the plate counters are not empty
   - the A2A command above
4. **Only if you changed overlay wording:**
   ```bash
   uv run python -m scripts.warm_overlay_text
   uv run python -m scripts.push_cache
   ```
5. **Pre-check from a logged-out window.** `/health` returns ok. `/agents/health` returns `"enabled": true`, with `killed: false` and `breaker_open: false` on every agent. The live page loads in under 3 seconds.

Do not warm the chaos question. A repeated question comes back from the cache and never touches the killed agent. Rehearse with one question, record with a different one.

## Keep it ready for the recording

1. **One API replica while you record.** The kill state and the "agents finished" state live in memory inside each API replica. With two replicas the page can poll one while you press the switch on the other, and nothing seems to happen. For the recording only: `az containerapp update -n ca-api-uirzml34ufpge -g pitchside --min-replicas 1 --max-replicas 1`. Check the names first with `az containerapp list -g pitchside -o table`. Put it back to two straight after (`--min-replicas 2 --max-replicas 3`) and keep it there until 10 Nov. This comes from reading the code, so confirm it in rehearsal.
2. **Do not burn the rate limits.** Fresh agent runs are 5 an hour for the whole service, Ask is 12 a minute, the chaos switch 10 a minute. Start the agents once. A retake does not need a new run.
3. **Do the chaos shot last in each take.** The switch lasts 30 seconds. Wait for the plate to return to normal before the next take.
4. **Choose the exact start minute for each scene in rehearsal** and write it on a sticky note, so every take lands on the same shot.
5. **Screen set-up.** 1920x1080, 60 fps, browser zoom 125%, bookmarks and other tabs hidden, notifications off. Pick light or dark and keep it for the whole video.
6. **Show the address bar once**, at 0:00 or at the close, so it is clear this is the deployed Azure site and not localhost.
7. **Read the script aloud with a timer.** Under 1:55 spoken, or cut words.

## Edit

Cut every pause. Burn in the captions from the table (many judges watch muted). Zoom into overlays so they read on a laptop. No music. Upload to YouTube as **public**, not unlisted.

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
- [ ] Budget alert active, uptime test active, API min replicas back at 2 until 10 Nov
