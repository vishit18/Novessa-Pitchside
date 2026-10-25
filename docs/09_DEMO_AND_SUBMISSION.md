# Demo video and submission

## The video (target 1:55, hard limit under 2:00)

Judges may stop at 2:00 and may judge from the video alone, so every second has to show something working. VJ records his own voiceover (sounds human, which matters). No music, or a track with a clear free-for-commercial-use licence logged in `docs/ASSET_LICENSES.md`. Record from the **deployed Azure URL**, with the browser address bar visible at least once.

| Time | Shot | Voiceover (rough, VJ rewrites in his own words) |
|---|---|---|
| 0:00–0:08 | Broadcast view, match running, an overlay slides in | "Millions of people watch the same match. They all get the same broadcast. They shouldn't." |
| 0:08–0:20 | Quick pull back: engine streaming events, numbers ticking in the Control Room | "This is a fully synthetic league. Every pass, tackle and sprint is generated live, so there's no real match data anywhere." |
| 0:20–0:35 | A pressure shift happens. Instant pass-difficulty and speed tags, then the "why" card lands | "Stats show up instantly. A couple of seconds later the agents explain why it matters, and every claim gets checked against the numbers before it airs." |
| 0:35–0:55 | **Split view**: Analyst/English vs Casual/Spanish on the same moment, with Spanish voice commentary | "Same moment, two viewers. The analyst gets the pressing numbers. My mate who just wants the story gets it in Spanish, out loud." |
| 0:55–1:08 | Player focus mode, then one-number mode | "Follow one player all match. Or pick the one number you care about." |
| 1:08–1:25 | **Real footage**: an openly licensed amateur match, players tracked and tagged by team, sprint speeds measured automatically, scrub the clock, then the scorecard (players found 71%, position error about 1 m, speed error about 3 km/h) | "And it's not just synthetic. This is a real amateur match from an open dataset. The same overlay idea, detected straight from video, and scored against the dataset's own labels. Players are strong. The ball is the weak spot, and we say so." |
| 1:25–1:42 | Control Room: agent graph lighting up, Verifier rejecting a claim, then the **chaos switch** kills the Analyst and the system recovers | "A team of agents built on Microsoft Agent Framework and Foundry. Kill one mid-match and the others carry on. Nothing breaks on screen." |
| 1:42–1:52 | Recap page in Arabic, then the A2A call returning a recap | "At full time, recaps for every persona and language, available to other agents over A2A." |
| 1:52–1:58 | Wordmark, repo URL, Azure services strip | "Novessa Pitchside. Same match. Your story." |

Tips: record at 1920×1080, 60 fps. Zoom in on overlays in the edit so they're readable on a laptop. Add burned-in captions (judges often watch muted). Trim every pause.

## Project pitch (hackathon page), draft

**Novessa Pitchside — Same match. Your story.**

Millions of people watch the same match and get the same broadcast, whether they live for pressing stats or just want to know why their team looks rattled. Novessa Pitchside gives each viewer their own version of the game, live, in their own language.

A synthetic engine plays a full 90 minutes in a fictional league. A deterministic stats layer turns it into momentum, control and chaos, pressure and pass difficulty, and puts instant overlays on screen in under 150 ms. A newsroom of agents built with Microsoft Agent Framework on Microsoft Foundry does the rest: a producer picks the moments, an analyst explains why they matter, and a verifier recomputes every number before it airs. A model never calculates anything. If a claim fails, the viewer gets the plain numbers. Other agents write for each viewer, translate and voice it in six languages, recap the match, and answer questions without spoiling the minute you are on. Kill any agent mid-match and the broadcast carries on.

The output is a timed overlay protocol any graphics engine could render. Analysts, casual fans, first-timers and audio-description users each get a different picture and different words, built around their club, their player or the one number they care about. We also pointed the same idea at a real amateur match from an open dataset: it tracks players and measures speeds from video, scored against the dataset's own labels.

It runs on Azure with a live link, scaled and load-tested (150 viewers, no errors), and every resource is Bicep.

**Built with:** Microsoft Foundry, Microsoft Agent Framework, A2A, our own MCP server, Azure MCP, Azure Container Apps, Azure Static Web Apps, Azure Event Hubs, Azure Cosmos DB, Azure Blob Storage, Azure AI Translator, Azure AI Speech, Azure AI Content Safety, Azure Monitor and Application Insights, Azure Load Testing, Key Vault, Bicep and the Azure Developer CLI, GitHub Actions and GitHub CLI.

_(Keep this under ~300 words. VJ rewrites anything that doesn't sound like him.)_

## Submission checklist (do it from a logged-out browser on Tue 27)

- [ ] Video < 2:00, public on YouTube, URL on the project page
- [ ] Repo public, README renders, licence present, no secrets, VJ is the only author on every commit
- [ ] Live URL loads with no login in under 3 seconds; testing instructions on the page
- [ ] Pitch names the Microsoft/Azure tech
- [ ] Project linked to the challenge
- [ ] Budget alert active, uptime test active, min replicas set until 11 Nov
