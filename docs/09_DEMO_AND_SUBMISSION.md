# Demo video and submission

## The video (target 1:50, hard limit under 2:00)

Judges may stop at 2:00 and may judge from the video alone, so every second has to show something working. Record from the **deployed Azure URL** with the address bar visible at least once. VJ records the voiceover himself, in his own words. No music, or a track whose free commercial licence is logged in `docs/ASSET_LICENSES.md`.

The shape: open on the problem, prove it in the first 35 seconds, show the part nobody else will have (the verifier, and killing an agent), then the real footage, then the Azure stack and the responsible AI line, then close on the line. About 240 spoken words. If a take runs long, cut words, never the shots.

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

### The cut (target 1:50, spoken about 240 words)

Before the first take, click once anywhere on the page. Browsers block sound until you do, and the Spanish voice in scene 4 needs it. If a "Tap to hear the commentary" button shows up, that is the browser asking for the click.

| Time | Where to be | What to do | Voiceover | Caption burned in |
|---|---|---|---|---|
| 0:00-0:07 | `/watch?match=derby_01&speed=4`. Drag the timeline to about 26:20. | Let the penalty and goal play. The name tag and shot-speed overlay appear instantly. | "Millions of people watch the same match and get the same broadcast. A tactics nerd and a first-timer see exactly the same thing." | Same match. |
| 0:07-0:16 | `/control?match=derby_01` | Scroll so one overlay message in the feed is in shot, large enough to read. | "This is Novessa Pitchside. A made-up league, no real club or player. Every graphic is a timed message a broadcaster can render, built in about 50 milliseconds." | Synthetic data. Machine-readable overlays. |
| 0:16-0:30 | `/watch?match=derby_01`. Drag to about 01:50 and let it run past 02:00. | The instant overlay lands, then the "Ashford lift the pressure" card. Cut to the Control Room moment queue for that moment, with "verifier: 3/3 claims proven" in the trail. | "A producer agent picks the moment, an analyst explains it, and a verifier recomputes every number before it airs. If a claim fails, the viewer gets plain figures." | Nothing airs unchecked. |
| 0:30-0:46 | `/split?match=derby_01` (it opens about 40 s before the first goal). Left: Analyst, English. Right: First match, Spanish, voice on. | Play through the 26:47 goal. Left shows pressing halos and evidence chips. Right shows the big direction arrow, no shirt numbers, Spanish text and voice. | "Same moment, two viewers. The analyst gets pressing lines and numbers. The new fan gets the story, in Spanish, out loud." | Your story. |
| 0:46-0:54 | `/watch?match=derby_01`, drag to about 45:00 | Player focus on Zakaria Tazi: the camera follows and the card shows his speed, distance and passes with ranks, such as "#3 of 8". He is a midfielder. Then pick "Just one number", sprint speed. | "Follow one player all match, or pick the single number you care about." | One player. One number. |
| 0:54-1:06 | `/real` | Play, let a sprint speed appear, scrub the clock once, end on the scorecard (players found 71%, position error about 1 m). Keep the SoccerTrack v2 credit in shot. | "Real video too, from an open amateur dataset: players tracked, speeds measured, scored against its labels. Players are strong. The ball is the weak spot, and we say so." | Real footage, CC BY 4.0. Players found 71%. |
| 1:06-1:22 | `/control?match=derby_01&t=4830` (clock 77:22) | Open the 77:17 moment: first draft rejected for using club codes, second proven. Press **Switch off for 30 s** on the Analyst plate. Go to the broadcast, press `/` and ask a question nobody has asked before. | "The verifier caught this draft and sent it back. Now I switch the analyst off. The broadcast keeps playing, and a new question gets plain numbers." | Switch an agent off. Nothing breaks. |
| 1:22-1:32 | `/why`, scroll to "What does the work" | Slow scroll so the service names are readable. | "It runs on Microsoft Foundry and Agent Framework, Azure Container Apps, Event Hubs, Cosmos DB, Content Safety, Translator and Speech, with an MCP server. All Bicep." | Foundry. Agent Framework. Azure. |
| 1:32-1:40 | `/watch?match=derby_01&t=325`. Viewer type: Audio-described. | Wait for the yellow card: the voice plays and the caption stays on screen between cards. | "Every line passes Content Safety. A red team assumes the model is hijacked: 14 of 14 attacks held. And there is an audio-described mode with captions." | Content Safety. 14 of 14 attacks held. |
| 1:40-1:47 | `/recap?match=derby_01&kind=full_time&persona=analyst&lang=ar` | Show the Arabic recap right to left. | "Recaps in six languages, and other agents can ask for them over A2A." | 6 languages. A2A. |
| 1:47-1:52 | Wordmark over the broadcast | Live URL and repo URL on screen. | "Novessa Pitchside. Same match. Your story." | Live on Azure. 150 viewers, 0 errors. All Bicep. |

The A2A call is optional footage. If you want to show it, this is the deployed Recap Editor:

```bash
uv run python -m scripts.a2a_client https://ca-a2a-uirzml34ufpge.salmonocean-c33a3a80.swedencentral.azurecontainerapps.io "Full-time recap for derby_01 in Arabic"
```

Run it once before recording and check it answers. If it is slow, record the terminal separately and cut it in, or skip it and keep the spoken line.

### Two clocks (read this before you drag any timeline)

`t=` in a URL is match seconds, counted straight through. The clock on screen stops for half-time stoppage and runs on, so after the break the two differ by about three minutes. The moment you want is in the clock column, the URL needs the seconds column.

| Moment | Clock on screen | `t=` seconds |
|---|---|---|
| Pressure shift | 02:00 | 120 |
| Penalty, then goal | 26:33, 26:47 | 1593, 1607 |
| Tazi's pass | 45:07 | 2894 |
| Red card | 71:45 | 4493 |
| Penalty with the rejected draft | 77:17 | 4825 |
| Penalty saved | 77:31 | 4839 |

The Control Room only lists moments the viewer has reached. `t=4640` stops at clock 74:10 and the 77:17 moment is not there. Use `t=4830`.

### Before every take (five minutes, do it in this order)

1. **One replica.** `az containerapp replica list -n ca-api-uirzml34ufpge -g pitchside -o table` shows one row. After any crowd it takes about five minutes to get back to one. With two or three replicas the Control Room can read a different replica on every refresh.
2. **Warm start.** Open `/control?match=derby_01&t=4830`. If the Moments panel says "No moments yet", press **Start the agents**. It takes about 22 seconds and ends on "Moments processed 28 of 28". You should then see 20 moments, newest first, with 77:17 on top. This uses one of the five fresh runs an hour.
3. **Click once on the page** you are about to record, so the browser allows sound.
4. **Chaos check.** Do not press the switch in rehearsal more than once or twice. It is rate limited, and the state clears itself after 30 seconds.
5. **Hard refresh** (Ctrl+Shift+R) each page right before the shot so the clock starts where you expect.

### What you will see, scene by scene (all checked on the live site on 26 Oct)

1. **0:00 Watch, 4x, around 26:20.** The pitch, the score bug at 0-0, then the penalty at 26:33 and the goal at 26:47. The goal band lands first, then the lower third "Wragg scores penalty" and a name tag. At 4x the whole thing passes in about 8 seconds.
2. **0:07 Control Room overlay feed.** A list of rows (time, slot, headline, who it is for). Click a row and the JSON for that overlay appears under it, with the line "Renders as: lower third, for 00:07 from 77:17". Click the 77:17 row for a readable example.
3. **0:16 Watch around 01:50, then the moment queue.** The instant overlay lands, then the "why" card (its headline depends on the viewer type). In the Control Room the 02:00 moment is the row "Ashford lift the pressure", marked "Proven".
4. **0:30 Split view.** Opens at 26:12, with Viewer 1 as "Analyst, English" and Viewer 2 as "First match, Español" already. The Spanish text is automatic. The Spanish voice needs you to switch Viewer 2's commentary on once, and the page click from step 3 of the checklist. The goal at 26:47 is the one to rely on.
5. **0:46 Player focus.** Zakaria Tazi (ASH-06) is a **midfielder**, not a forward. His card shows speed, distance, passes and shots with ranks, for example "5.54 km, #3 of 8" and "Passes 35/43, #2 of 8". Do not call him a forward.
6. **0:54 Real footage.** A 100-second window from 31:30 to 33:10, with "Footage: SoccerTrack v2 (CC BY 4.0)" under the video, then the list of passes it found (for example "White player to white team-mate, 23 m, 53 km/h, difficulty 33"). The scorecard is lower on the page: players found 71%, position error about 1 m. Scroll to it before you start talking about it.
7. **1:06 Control Room at `t=4830`.** The 77:17 moment sits at the top of the list as "Wragg to take the penalty, Proven on retry". Click it and the trail reads, in this order:
   - "verifier rejected (attempt 1): use club names, never their codes"
   - "verifier: 3/3 claims proven (attempt 2)"
   - "narrator text rejected: Viggo Falkman committed the foul; he was not fouled"
   - "served from cache"

   Then press **Switch off for 30 s** on the Analyst plate and go to the broadcast (see "Switching the Analyst off" below).
8. **1:22 `/why`, "What does the work".** The list of Azure and Microsoft services with a status dot for each. Scroll slowly. The Event Hubs line says 140 ms p95 in a one-off job and over budget on the busy replicas. That is true, so do not linger on it.
9. **1:32 Audio-described.** Pick "Audio-described" as the viewer type, start at `t=325`. The yellow card at 05:31 shows "Early caution for Balogun", the voice reads it, and the caption strip stays at the bottom of the pitch after the card fades. If the voice is silent and a yellow "Tap to hear the commentary" button shows, click anywhere.
10. **1:40 Arabic recap.** The page is right to left. The Arabic recap was opened on the live site on 26 Oct, so it now loads in well under a second. If the cache is ever cleared it shows "Writing the recap" for about 15 seconds first. The key-moments list under the headline is in English, the body and highlights are Arabic.
11. **1:47 Close.** Wordmark over the broadcast, then the URL.

### If something looks wrong

| You see | Why | What to do |
|---|---|---|
| Control Room says "No moments yet" | The agents have not run on this replica, or the API restarted or scaled | Press **Start the agents**, wait 22 s |
| Control Room counters differ between refreshes | More than one API replica is up | Wait for one replica, refresh |
| Plate does not turn red when you press the switch | Same cause: you pressed it on one replica and the page read another | Same fix, then press again |
| The Ask answer is a full sentence while the Analyst is off | The question was asked before and came from the cache, or it reached another replica | Use a new question, check one replica |
| No voice | Browser blocked sound until a click | Click the page, or the yellow "Tap to hear" button |
| First Arabic recap shows skeleton bars for 15 s | Cache was cold | Wait, then retake |
| A page is slow for a few seconds after you start | The API had scaled down to one replica and a lot of people are on it | Wait 30 s and retry |

### What to expect, and what to do if it does not happen

- **Instant overlays** (name tag, shot speed, pass difficulty) arrive with no model call. If one is missing, the page is not connected: hard refresh and start the scene again.
- **The "why" card** comes after the instant overlay. For every moment in the table it is served from the cache, so it should land in under a second. If it takes 4 s or more, the cache is cold: see "Warm everything".
- **Split view in Spanish.** Rely on the 26:47 goal and the 45:07 pass. Other moments may arrive in English if they were never translated.
- **The Verifier rejection.** Only 77:17 is a recorded Verifier rejection on this match ("use club names, never their codes", then 3 of 3 proven). 05:31 and 26:33 show the *narrator* being rejected, which is also fine on screen but is a different line in the trail. Open 77:17.
- **Switching the Analyst off.** Tested against the live API on 26 Oct. Press **Switch off for 30 s** on the Analyst plate in the Control Room.
  - The plate's bar goes red, its status reads "Switched off" and its button reads "Recovering". After 30 seconds it returns to "Healthy" by itself.
  - The same press switches off the agent behind Ask the Analyst, which runs as its own agent called `ask`. Before 26 Oct the plate did not do this, so Ask kept answering normally.
  - Cached moments keep arriving, because a cached moment never calls a model. That is the point: the broadcast does not stop. Do not expect a visible change on the pitch.
  - Press `/` on the broadcast within the 30 seconds and ask a question nobody has asked. You should get a short answer that starts "Here is what the data shows." followed by plain figures, for example "Kestrel Bay FC passes, last 38 minutes: 235; ...". The label under it reads "Straight from the numbers: the wording could not be checked". In "How this was worked out" the last line is "Analyst unavailable: answered with the numbers only".
  - A normal answer to a similar question is a full sentence with a green tick and "Checked against the match data". That contrast is the shot.
  - The switch applies to one API replica. With two replicas, about one question in four reaches the other and gets a normal answer. Record with one replica (see "Keep it ready for the recording").
  - A question someone has asked before comes back from the cache and ignores the switch. Use a fresh question every take.
  - The switch is capped at 30 seconds and limited to 10 presses a minute for the whole service.
- **Audio-described scene.** The voice needs a click on the page first. If you see the yellow "Tap to hear the commentary" button, click anywhere and the waiting line plays. The caption strip sits at the bottom of the pitch whenever no card is on screen.
- **Arabic recap.** Warmed on the live site on 26 Oct, so it opens in well under a second. If the cache is ever cleared the first open takes about 15 seconds, with skeleton bars and "Writing the recap".

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

1. **One API replica.** The kill state and the "agents finished" state live in memory inside each API replica, so with two replicas the page could poll one while you pressed the switch on the other. On 26 Oct the API was set to min 1, max 3 and tested: eight health reads after a kill all showed the agent switched off, and four fresh questions all came back as plain numbers. Check it is still one before recording: `az containerapp replica list -n ca-api-uirzml34ufpge -g pitchside -o table` should list one row. After a scale-down it takes about five minutes for the second replica to go. Keep min 1 until 10 Nov. (`API_MIN_REPLICAS=1` in `azd env`, so a later `azd up` keeps it.)
2. **Do not burn the rate limits.** Fresh agent runs are 5 an hour for the whole service, Ask is 12 a minute, the chaos switch 10 a minute. Start the agents once. A retake does not need a new run.
3. **Do the chaos shot last in each take.** The switch lasts 30 seconds. Wait for the plate to return to normal before the next take.
4. **Choose the exact start minute for each scene in rehearsal** and write it on a sticky note, so every take lands on the same shot.
5. **Screen set-up.** 1920x1080, 60 fps, browser zoom 125%, bookmarks and other tabs hidden, notifications off. Pick light or dark and keep it for the whole video.
6. **Show the address bar once**, at 0:00 or at the close, so it is clear this is the deployed Azure site and not localhost.
7. **Read the script aloud with a timer.** Under 1:45 spoken, or cut words.

## Edit

Cut every pause. Burn in the captions from the table (many judges watch muted). Zoom into overlays so they read on a laptop. No music. Upload to YouTube as **public**, not unlisted.

## Project pitch (hackathon page)

**Tagline.** A broadcast layer that turns live football events into fact-checked, explained insights, personalised for each viewer. Built with AI agents on Microsoft Foundry and Azure.

**Description.**

Everyone watching a match gets the same broadcast. A fan who follows pressing stats and someone watching their first game see the same graphics and hear the same analysis, because broadcasters can only produce one feed. Novessa Pitchside gives each viewer their own version of the match, live and in their language.

A synthetic engine plays 90 minutes in a fictional league. A stats layer turns the events into numbers like momentum, pressure and pass difficulty, and builds the overlays in about 50 ms with no model call.

Agents built with Microsoft Agent Framework on Microsoft Foundry then work like a small newsroom. One picks the key moments, one explains them, and a verifier recomputes every number before it goes out. The language model never does the maths. If a claim doesn't check out after one retry, the viewer sees the raw numbers instead, so every number in the English text can be traced back to the data. Seven of the agents call a model; the Verifier and Story Keeper are plain code on purpose, so they cannot be talked round. Other agents tailor what each viewer sees and reads, translate and voice it in six languages, write the recap, and answer questions without spoiling what's ahead.

The output is a timed overlay format, so a broadcaster's existing graphics engine could render it.

It runs on Azure Container Apps, Cosmos DB and Static Web Apps, with Azure AI Translator, Speech and Content Safety. The live path runs through Event Hubs: the engine publishes, the gateway consumes, and we sent 19,830 messages through it and lost none. The broadcast you open in the demo is a replay of the same events, read from a timeline prepared by the same code, so anyone can scrub it. The recap agent is open to other agents over A2A, and our stats layer is also an MCP server, so outside tools can ask the same questions our agents do. We built and managed the Azure side with Azure MCP. Everything is defined in Bicep and deploys with azd. We load-tested the API with 150 concurrent viewers and saw no errors, and the broadcast keeps running if any agent goes down. There is an audio-described viewing mode with spoken commentary and captions. Every line passes Azure AI Content Safety before it airs, and a red team that assumes the model is hijacked runs in CI: 14 of 14 attacks held.

It is built for broadcasters and streaming platforms: one feed in, a broadcast per viewer out.

We also tried it on a real amateur match from the open SoccerTrack v2 dataset, used under its CC BY 4.0 licence with credit to its authors, tracking players and their speeds from video.

Live demo: https://ashy-pebble-0f5b51c1e.5.azurestaticapps.net · Code: https://github.com/vishit18/Novessa-Pitchside

_(VJ rewrites anything that doesn't sound like him. Check the form's length limit before pasting.)_

## Submission checklist (do it from a logged-out browser on Tue 27)

- [ ] Video under 2:00, public on YouTube, URL on the project page
- [ ] **Repo public** (rules §4.4: required for the entry to count), README renders, licence present, no secrets, no footage files
- [ ] Live URL loads with no login in under 3 seconds; testing instructions on the page
- [ ] Pitch names the Microsoft and Azure tech
- [ ] Project linked to the challenge
- [ ] Team members listed on the submission, with no personal data in the text
- [ ] Budget alert active, uptime test active, API min replicas 1 (max 3) until 10 Nov
