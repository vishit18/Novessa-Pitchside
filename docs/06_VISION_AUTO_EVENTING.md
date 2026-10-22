# Vision auto-eventing (real footage)

Brief: "running a model over an incoming video feed to generate the pass and speed metrics automatically, rather than tagging them by hand."

Rules §4.7: footage is allowed, but we must source it ourselves and hold the rights. And rules §7 gives Microsoft and the Premier League a perpetual, commercial licence to use our submission. So any footage in the demo has to be licensed for **commercial use with attribution at most**. That rules out:
- any professional or lower-league match footage, highlights or YouTube clips (owned by broadcasters, clubs or leagues), unless a club gives us written permission
- non-commercial datasets (CC BY-NC), e.g. SportsMOT
- research-only datasets behind an NDA, e.g. SoccerNet video

**Priority P1. Build it after the synthetic pipeline works end to end.** Time-box it to about 1.5 days. If it slips, the synthetic system still stands on its own.

## Footage source: SoccerTrack v2 (CC BY 4.0)

**What this data is, precisely:** real video of real university matches, plus human-made labels (player positions, jersey numbers, ball events). The only reconstructed part is the `ball` track, which is interpolated between labelled events rather than measured. None of it is synthetic, and none of it touches the synthetic engine or the main match experience. See the "Keep real and synthetic strictly apart" rule in `CLAUDE.md`.

- Hugging Face: `atomscott/soccertrack-v2` (gated: VJ logs in and accepts the conditions). Paper: arXiv 2508.01802. Code: github.com/AtomScott/SoccerTrack-v2.
- 10 full-length **university-level amateur** matches, 4K **panoramic full-pitch** video (BePro cameras). A fixed full-pitch view is ideal: one homography covers the whole clip.
- Comes with **ground truth**: 2D pitch coordinates per player, track IDs, team side, jersey numbers, and ball action labels for 12 event classes. That means we can *measure* how good our auto-eventing is. Most entries can't.
- Pseudonymised: players are jersey numbers and IDs only, no names. So our tags show **team + number** (e.g. "Blue #7"), never invented real-sounding names on real people.

### Before using it (VJ, 10 minutes, do it Tuesday)
1. Accept the conditions on the Hugging Face page and **read them**. If anything there forbids public demos or commercial use, stop and tell Claude Code; we switch to the fallback below.
2. Check frames for visible sponsor logos or club badges. If any are obvious, either pick a clip where they're not readable or blur them in preprocessing (`vision/redact.py`, simple fixed-region blur).
3. Add the attribution to `docs/ASSET_LICENSES.md`, the README credits, and a small on-screen credit in real-footage mode: "Footage: SoccerTrack v2 (CC BY 4.0)".

### Download only what we need (~6 GB once, ~150 MB kept)

**Never download the whole 145 GB repo.** We use one match, one half: match `117093` (paper label M2), 1st half. Pull only these files with the `hf` CLI (VJ runs `hf auth login` once with a read token):

```bash
mkdir -p footage/raw && cd footage/raw
hf download atomscott/soccertrack-v2 --repo-type dataset --local-dir . \
  --include "videos/117093/117093_panorama_1st_half.mp4" \
            "gsr/117093/117093_1st.json" \
            "bas/117093/*" \
            "ball/117093/*" \
            "raw/117093/117093_homography.npy" \
            "raw/117093/117093_keypoints.json" \
            "raw/117093/117093_camera_intrinsics.npz" \
            "raw/117093/117093_padding_info.csv" \
            "raw/117093/117093_map*.npy" \
            "README.md" "CHANGES_v1_2.md"
```

| File | Size | Why |
|---|---|---|
| 1st-half panorama video | 3.35 GB | the footage |
| `gsr` 1st-half JSON | 2.71 GB | ground truth player positions, jersey numbers, team sides |
| `bas` events | ~0.5 MB | ground truth passes, shots etc. with frame numbers |
| `ball` track | small | ground truth ball path (interpolated between events) |
| `raw` calibration | ~27 MB | **ready-made homography and 65 hand-annotated pitch keypoints**, so no manual calibration clicking |

Then `scripts/prepare_footage.py`:
1. Pick a lively 90–120 s window (use `bas` events to find one with a few passes and a shot).
2. Cut it with ffmpeg and downscale for the web (e.g. 4096×1080 → 2560×675, H.264, ~5 Mbps) → about 50–80 MB.
3. Stream-parse the 2.7 GB GSR JSON with `ijson` (never `json.load` it) and keep only frames in the window → a few MB.
4. Slice `bas` and `ball` to the window.
5. Delete the big originals.

What we keep: the short clip + small ground-truth files. Only the short clip goes to Azure Blob. Footage stays out of git.

The vision model runs **once, offline** on that window. The deployed app only plays the clip and streams the pre-computed events, so there's no load on Azure and no GPU needed in the cloud.

Notes on this footage:
- Panorama is 4096×1080 at 25 fps, so players are small and the ball is tiny. Run detection on overlapping tiles (e.g. 3–4 tiles across) or upscale crops; test this on 10 seconds first.
- Coordinates in GSR are metric, 105 × 68 m, **origin at the centre circle**. Our schema uses origin bottom-left, so convert.
- The `ball` track is a reconstruction interpolated between events, not measured per frame. Use it for event timing; don't present it as true ball-speed ground truth. Our ball-speed numbers are our own measurement.
- There's also a `mot/clips` folder (4-minute 4096×1080 clips, ~3.6 GB total for all ten, with per-frame player boxes). Useful only if we want a standard MOT tracking score; optional.

### Fallbacks, in order
1. Wikimedia Commons football video with CC0 / CC BY licence (quality will be lower).
2. A local non-league or Sunday-league club that already films its matches (many use auto-cameras) and gives **written permission** for a public, commercially-licensed hackathon demo. Email takes days, so only start this if (1) and SoccerTrack both fail by Wednesday.
3. Drop real footage and run auto-eventing on **rendered synthetic video**: render our engine's match in 3D from a broadcast camera angle and detect from the pixels. Fully ours, on-theme, but detection on rendered players needs testing early.

## Pipeline (`vision/`)

All dependencies must be permissively licensed (Apache/MIT/BSD). **No Ultralytics YOLO (AGPL).**

1. **Detection:** RF-DETR (Apache 2.0) or RT-DETR via Hugging Face `transformers` (Apache 2.0), classes `person` and `sports ball`. Panoramic 4K frames: tile or downscale smartly so the ball isn't lost. Offline on GPU if VJ has one, else CPU on a short clip.
2. **Tracking:** ByteTrack from Roboflow `supervision` (MIT). Ball tracked separately with interpolation for missed frames.
3. **Team assignment:** torso colour k-means (k=2) plus a referee/other cluster.
4. **Pitch calibration (homography):** use the dataset's own `homography.npy`, keypoints and undistortion maps. No manual clicking needed. Keep `vision/calibrate.py` (click 4+ points) only for any other footage source.
5. **Identity:** team + jersey number. Use the dataset's labels only to *evaluate*, never as an input to the pipeline at runtime. Jersey-number OCR is optional; a one-off click-to-label tool is fine and honest.
6. **Kinematics:** speeds from smoothed (Savitzky–Golay) pitch positions; distance covered; ball speed; shot speed from the first frames after the strike.
7. **Event detection (rules on tracks):**
   - possession = nearest player to ball within 1.5 m for > 0.3 s
   - **pass** = possession moves between same-team players → distance, ball speed (distance over flight time between the two touches; flights under 0.4 s and anything over 100 km/h are left blank), accuracy
   - **possession change / tackle** = possession moves to the other team
   - **shot** = ball moving fast toward a goal
   - pressure = opponent within 3 m of the ball carrier
8. **Output:** the *same* `MatchEvent` and tracking schema as the synthetic engine, `source: "vision"`, published to the same event bus. State engine, agents and overlays work unchanged. That's the production story: swap our synthetic feed for a real tracking provider and nothing else changes.
9. **Pass difficulty** on real passes uses the same model from `docs/03` §5.

## Validation against ground truth (make this a headline number)

`vision/evaluate.py` compares our output with SoccerTrack v2 labels on the chosen segment:
- player position error (metres, median and p90)
- pass detection precision / recall vs labelled passes
- speed error where computable

Put the table in the README and flash it for a couple of seconds in the video. Honest numbers beat impressive claims.

## Render

"Real footage" mode plays the video with overlays drawn via the inverse homography: team + number tags following players, speed bursts, pass difficulty cards, ball-speed callouts. Overlays sync to the video via `t_match`. Small attribution credit in the corner.

## Azure angle

Package as a container and define it as an **Azure Container Apps job** that reads video from Blob Storage and publishes events to Event Hubs. Run it locally for development if faster, but the job definition in Bicep shows the production path.
