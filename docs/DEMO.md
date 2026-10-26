# The demo video

1:50, recorded from the live Azure site. Every synthetic-match shot is `derby_01`, Ashford Rovers v Kestrel Bay, which ends 2-1. All agent text in it was verified and cached before recording, so a replay costs nothing.

| Time | What you see | Try it yourself |
|---|---|---|
| 0:00 | The same penalty for two viewers: an analyst, and a first-time fan watching in Spanish | `/split?match=derby_01` |
| 0:11 | Make it yours: club, language, viewer type. Player focus on Tazi, then a single number on screen | Watch, then "Watching as" |
| 0:23 | Ask the analyst. It only knows the match up to your minute, and the answer is checked against the data | Press `/` on Watch |
| 0:33 | The Verifier catching the narrator getting a foul backwards, before it aired | `/control?match=derby_01` |
| 0:46 | The Analyst switched off mid-match. The match carries on and Ask answers from the numbers | Chaos switch in the Control Room |
| 0:58 | The phone view catching you up on what you missed, up to your minute | `/companion?match=derby_01&speed=10` |
| 1:05 | The same system on real amateur footage, and how it scores against the dataset's labels | `/real` |
| 1:17 | Audio-described mode, the app in Hindi, a recap in Arabic | Watch, then "Watching as" |
| 1:24 | The overlay feed a broadcaster's graphics engine would receive | Overlay feed in the Control Room |
| 1:30 | The Azure and Microsoft services behind it | `/why` |

The voiceover is a team member's voice, cloned from their own recording. The only sound effect is our own, made in code (`docs/ASSET_LICENSES.md`). The footage in the real-footage scene is SoccerTrack v2, CC BY 4.0, credited on screen.
