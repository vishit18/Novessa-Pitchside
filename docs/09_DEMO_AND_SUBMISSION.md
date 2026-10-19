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
| 1:08–1:25 | **Real footage**: an openly licensed amateur match, players tagged by team and number, ball speed and pass difficulty measured automatically, accuracy vs ground truth flashed up | "And it's not just synthetic. This is a real amateur match from an open dataset. Same agents, same overlays, detected straight from video, and checked against the dataset's ground truth." |
| 1:25–1:42 | Control Room: agent graph lighting up, Verifier rejecting a claim, then the **chaos switch** kills the Analyst and the system recovers | "Eight agents built on Microsoft Agent Framework and Foundry. Kill one mid-match and the producer reroutes. Nothing breaks on screen." |
| 1:42–1:52 | Recap page in Arabic, then the A2A call returning a recap | "At full time, recaps for every persona and language, available to other agents over A2A." |
| 1:52–1:58 | Wordmark, repo URL, Azure services strip | "Novessa Pitchside. Same match. Your story." |

Tips: record at 1920×1080, 60 fps. Zoom in on overlays in the edit so they're readable on a laptop. Add burned-in captions (judges often watch muted). Trim every pause.

## Project pitch (hackathon page), draft

**Novessa Pitchside — Same match. Your story.**

Every fan watching a match gets the same broadcast, whether they live for pressing stats or just want to know why their team suddenly looks rattled. Novessa Pitchside gives each of them their own version of the game, live.

A synthetic engine streams a full 90 minutes of football from a fictional league: passes, tackles, sprints, pressure, all of it. A deterministic stats layer turns that into momentum, control vs chaos, pressure shifts and pass difficulty in under 150 ms. Then a team of eight agents built with Microsoft Agent Framework on Microsoft Foundry takes over. A producer decides what's worth putting on screen. An analyst explains why it matters. A verifier checks every claim against the numbers before it airs. Others write it for each kind of viewer, translate it, voice it and recap it. If one agent fails mid-match, the others route around it.

The output is a timed overlay protocol that any graphics engine could render. Analysts, casual fans, first-timers and people using audio description each get a different experience in their own language, built around their club, their player, or the one number they care about. We also pointed it at a real amateur match from an open dataset, and it tags players and measures pass and shot speed straight from video, checked against the dataset's ground truth.

**Built with:** Microsoft Foundry (models, agent tracing, evaluations), Microsoft Agent Framework, A2A, our own MCP server, Azure MCP, Azure Container Apps, Azure Event Hubs, Azure Cosmos DB, Azure Static Web Apps, Azure AI Translator, Azure AI Speech, Azure AI Content Safety, Application Insights, Key Vault, Bicep + Azure Developer CLI, GitHub Actions and GitHub CLI.

_(Keep this under ~250 words. VJ rewrites anything that doesn't sound like him.)_

## Submission checklist (do it from a logged-out browser on Tue 27)

- [ ] Video < 2:00, public on YouTube, URL on the project page
- [ ] Repo public, README renders, licence present, no secrets, VJ is the only author on every commit
- [ ] Live URL loads with no login in under 3 seconds; testing instructions on the page
- [ ] Pitch names the Microsoft/Azure tech
- [ ] Project linked to the challenge
- [ ] Budget alert active, uptime test active, min replicas set until 11 Nov
