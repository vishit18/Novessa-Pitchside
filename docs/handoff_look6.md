# Handoff: move the whole app to "Matchday broadcast" (look 6)

For whoever picks this up, human or Claude Code. Read this whole file, then `CLAUDE.md`, then
`docs/07_FRONTEND_DESIGN.md`, before touching code. CLAUDE.md's rules all still apply.

## The job

VJ chose look 6, "Matchday broadcast", from `/design-lab`. It replaces the current dark
"Floodlights" look across the whole frontend: every page, every on-pitch graphic, the pitch itself.

**This is a re-skin, not a redesign.** Same screens, same copy, same behaviour, same routes, same
components. Only colours, fonts, plate shapes, spacing tokens and entrance motion change. If you
think something's layout or wording should change, write it down and ask VJ. Don't do it.

See it first: run the app (below) and open `http://localhost:5173/design-lab?look=blend`. That
screen is the reference. Its exact values are in:

- `frontend/src/screens/lab/directions.ts`: the comment at the top (look 6) and the `blend` pitch palette
- `frontend/src/screens/lab/lab.css`: everything under `.lab-blend`, plus the phone rules

## Hard rules

1. **Frontend only.** Don't touch `backend/`, `engine/`, agents, the stats engine, the overlay
   protocol (`docs/05`) or any schema.
2. **Nothing breaks.** Every route still loads and behaves the same. `npm run lint`, `npm test`,
   `npm run build` and `npm run e2e` all pass at the end, exactly as they do now. Don't edit an e2e
   test to make it pass. If one fails, the app is wrong.
3. **Fictional league only.** No real clubs, league names, PL colours, crests or fonts. Look 6's
   red and yellow are fine. Don't add anything that resembles a real broadcaster's graphics package.
4. **No AI attribution** in commits, PRs, comments or docs (see CLAUDE.md). Team members commit
   under their own git identity. Never change someone else's, never `--author`, never force-push
   `main`.
5. **Work on a branch** (`look6-app` off `design-lab-and-why`) and open a PR. Don't push to `main`.
6. Overlay motion stays under 300ms, and `prefers-reduced-motion` still turns it into plain fades.

## Skills and tools to use (same workflow VJ uses)

Install on your machine first:

```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install frontend-design@claude-plugins-official
/plugin install microsoft-docs@claude-plugins-official
```

Ask VJ for copies of these skills from his `~/.claude/skills` and put them in yours:
`impeccable`, `taste-skill`, `emil-design-eng`, `review-animations`, `improve-animations`,
`animation-performance`, `animation-vocabulary`, `break-ui`.

The MCP servers in `.mcp.json` (Playwright, Microsoft Learn, Azure) load automatically. You need
Playwright for screenshots.

How to use them:

| When | Skill |
|---|---|
| Before any UI edit | `frontend-design` + `taste-skill` (direction, no generic look) |
| After each phase | `impeccable` critique, then `impeccable` audit (contrast, a11y, responsive) |
| Plate wipes, tags, sting, any motion | `emil-design-eng`, then `review-animations` |
| Janky motion on the pitch pages | `animation-performance` |
| Before calling it done | `break-ui` on Home, Watch and Companion (long names, Arabic, Hindi) |

Where `docs/07` and a skill disagree, `docs/07` wins. You'll be updating `docs/07` in step 1, so
it stays the source of truth.

## Run it

```bash
make dev                      # engine + backend + frontend, in-memory bus
# or, frontend only against a running gateway:
cd frontend && npm ci && npm run dev    # http://localhost:5173
```

The gateway defaults to `ws://127.0.0.1:8000`. If something else is on 8000, run the backend on
another port and start Vite with `VITE_GATEWAY_URL=ws://127.0.0.1:<port>`. Also add your Vite
origin to the gateway's `CORS_ORIGINS`, or match data won't load and the panes stay grey.

## Step 0: screenshots before you change anything

Take a full set of "before" screenshots and keep them outside the repo. You'll compare against them
at the end. Do this with no code changes made.

- Sizes: 1920×1080 and 390×844 for every route, plus 1280×720 for `/watch` and `/split`.
- Routes: `/`, `/start`, `/watch?match=derby_01&t=1611&speed=1`, `/split?match=derby_01&t=1611`,
  `/companion?match=derby_01`, `/control?match=derby_01`, `/recap?match=derby_01`, `/real`, `/why`.
  Also take `/watch` with an Arabic profile (RTL) and a Hindi profile.
- Wait about 6s after load so the pitch, score bug and first overlays are up.
- Write a small Playwright script for this (`@playwright/test` is already a dev dependency).
  Use `http://localhost:...`, not `127.0.0.1`, because Vite listens on IPv6.

## Step 1: update the art direction first

Rewrite the "Art direction" section of `docs/07_FRONTEND_DESIGN.md` from "floodlights" to
"Matchday broadcast". Use the values below. Keep the rest of the doc as it is. Commit this on its
own (`docs: art direction moves to matchday broadcast`).

## The look, as tokens

| Token (`index.css` `@theme`) | Now (Floodlights) | Look 6 |
|---|---|---|
| `--color-ink` (page) | `#0d1014` | `#eef1ed` |
| `--color-raised` | `#161b22` | `#ffffff` |
| `--color-hairline` | `#2a313b` | `#cfd6d0` |
| `--color-text` | `#e8edf2` | `#101418` |
| `--color-muted` | `#9aa5b1` | `#4f5a54` |
| `--color-amber` (the accent) | `#ffb020` | `#e4002b` on the page, `#ffd100` inside plates |
| `--color-pressure` | `#e05cff` | see "Semantic colours" |
| `--font-display` | Barlow Condensed | Big Shoulders Display 800, uppercase for headlines |
| `--font-sans` | Inter | Figtree 400/600 |
| `.num`, `.latin` | Barlow Condensed | Big Shoulders Display 800, keep `tabular-nums` |

- **Plates** (`.plate`: score bug, lower thirds, tags, cards, timeline, menus): solid `#101418`,
  parallelogram clip `polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)`, no inner
  highlight, shadow `drop-shadow(0 6px 12px rgb(16 20 24 / .35))`. Inside a plate, re-point the
  tokens to light ink: `--color-text:#fff; --color-muted:#b4bac2; --color-hairline:#2c3037;
  --color-raised:#1a1d22; --color-amber:#ffd100; color: var(--color-text);`.
- **Pitch**: in `components/pitch/palette.ts`, add a `MATCHDAY` palette with the values of `blend`
  in `directions.ts`. Make it the context default (`createContext(MATCHDAY)`). Keep `FLOODLIGHTS`
  exported, because the lab uses it.
- **Stage** (`.stage-bg`, behind the pitch): `#101418`. The pitch sits in a black frame, like a
  TV monitor.
- **Buttons**: primary is red `#e4002b` with white uppercase display text and the parallelogram
  clip, hover `#c40025`. Secondary is a `#101418` outline. Focus ring: 2px `#101418` with a 2px
  offset (red on light is low contrast for a ring).
- **Viewer labels** (split view): yellow tab for the first viewer, red tab for the second, sitting
  on top of the pane frame (see `.lab-blend .fl-who`).
- **Motion**: plates and tags wipe in left to right in 180ms (`fl-tag-wipe` in `lab.css`), and
  reduced motion falls back to fades. Nothing bounces.
- **Fonts**: move `@fontsource/big-shoulders-display` and `@fontsource/figtree` from
  devDependencies to dependencies and import them in `index.css`. Keep the Arabic (IBM Plex Sans
  Arabic) and Hindi (Noto Sans Devanagari) overrides exactly as they are. Drop the Barlow and Inter
  imports only once nothing references them. Licences are already in `docs/ASSET_LICENSES.md`.
  Update that row to say the fonts are now used app-wide.

### Semantic colours: decide, don't guess

On a light page, the current semantic colours need checking for WCAG AA contrast.
`control #5cc8ff` fails as text on `#eef1ed`. `chaos #ff4d4d` now clashes with the red accent.
Recommendation:

- Keep each colour where it's drawn on the pitch or inside black plates. They read fine there.
- Where they appear as text or thin lines on the light page, use darker variants that pass AA.
- Make chaos visibly different from the accent red.

Show VJ a swatch screenshot before committing to new values.

## Traps already found (don't rediscover them)

1. **Text inside black plates turns invisible.** Plain text inherits its *computed* colour from
   the page. Redefining `--color-text` on `.plate` isn't enough, so also set
   `color: var(--color-text)` on `.plate`. This is why the score disappeared in the first try at
   look 6.
2. **Yellow on the light page is unreadable.** Yellow only goes inside black plates and on the
   pitch. On the page, the accent is red.
3. **Hard-coded dark assumptions.** These files hard-code colours or `white/xx` / `bg-ink/xx`
   translucency that assumes a dark page. Check each one:
   `RealFootage.tsx` (13 hits), `PitchRenderer.ts` (palette only, already themable), `Hud.tsx` (10),
   `Timeline.tsx` (6, including the hover tooltip), `Recap.tsx`, `AskSheet.tsx`, `PlayerCard.tsx`,
   `FeedCard.tsx`, `Onboarding.tsx`, `Home.tsx`, `ViewerChooser.tsx`, `AgentGraph.tsx`,
   `AppNav.tsx` (menu button `border-white/30 bg-ink/70`), `GoalSting.tsx` (`bg-ink/92`),
   `CatchUpSheet.tsx`, `MomentsTimeline.tsx`, `ViewerChrome.tsx` (`hover:bg-[#1d242d]`),
   `chromeStyles.ts`, `StatBars.tsx`, `MicButton.tsx`, `ErrorBoundary.tsx`, `MomentQueue.tsx`,
   `Gauges.tsx`, `ControlRoom.tsx`, `Companion.tsx`, `Stage.tsx`.
   Find them with:
   `grep -rnE "(bg|text|border)-\[#|(bg|text|border)-(white|black)|bg-ink/|#[0-9a-fA-F]{6}" frontend/src`
   Anything that sits *on the pitch* (tags, sting, HUD over the canvas) can stay dark: make it a
   plate. Anything that sits *on the page* must work on light.
4. **The design lab depends on app tokens.** `.fl` in `lab.css` inherits the app's tokens, and the
   lab's "Floodlights" tab has no overrides. Before changing `index.css`, copy the current
   Floodlights token values into `.lab-floodlights` in `lab.css`, so the lab keeps showing the old
   baseline. Check `/design-lab` still shows all six looks correctly afterwards.
5. **Real footage mode** must keep the SoccerTrack v2 credit visible and legible (CC BY 4.0 rule
   in CLAUDE.md). Video frames are dark, so overlays there should be plates.
6. **Font loading.** Fontsource packages export `./*` → `./*.css`. Import without the extension
   (`@import '@fontsource/figtree/600';`). Adding `.css` fails the build.
7. **Arabic.** Big Shoulders has no Arabic glyphs. The `[lang='ar']` override must still win, and
   uppercase does nothing in Arabic, so check headlines don't rely on caps for hierarchy. Check RTL
   on `/watch`, `/split` and `/companion`.
8. **Ports.** Something else may already be on 8000. See "Run it".

## Order of work (one commit per step, screenshots after each)

1. `docs/07` art direction (above).
2. Pin Floodlights into `.lab-floodlights` (trap 4). Check the lab is unchanged.
3. Fonts and `@theme` tokens in `index.css`, the `.plate` / `.plate-chip` / `.stage-bg` rules, the
   focus ring. Screenshot everything. Expect breakage, which tells you where step 5 needs to go.
4. Pitch palette default (`palette.ts`).
5. Fix the hard-coded files from trap 3, page by page in this order: **/watch → /split → /** (the
   video's screens first), then /companion, /start, /recap, /control, /real, /why.
6. Motion: tag and plate wipes app-wide. `review-animations` on the result.
7. Semantic colours (after VJ signs off on the swatch).
8. `impeccable` critique and audit on every route. Fix P0/P1. `break-ui` on Home, Watch and
   Companion.
9. Final pass (below).

## Done means

- After screenshots at the same routes and sizes as step 0. Put each before/after pair side by
  side and go through them: layout, copy and behaviour are identical, only the look changed. Write
  down anything that moved and why.
- `npm run lint`, `npm test`, `npm run build`, `npm run e2e` all pass. `make test` passes
  (backend untouched).
- WCAG AA contrast on body text, muted text and every button (check with the `impeccable` audit).
- 1920×1080, 1280×720 and 390×844 all look right. Arabic RTL looks right.
- Reduced motion checked (Playwright `emulateMedia({ reducedMotion: 'reduce' })`).
- `docs/07` describes what shipped. Tick the matching boxes in `docs/00_REQUIREMENTS_CHECKLIST.md`
  if any change. Add a line to the Status section of `docs/08_BUILD_PLAN.md`.
- PR description: what changed, the before/after sheet, anything you weren't sure about. No AI
  attribution.

## Not in scope (ask VJ first)

- Replacing Home's content with the design lab's two-fans-live first screen. VJ hasn't decided
  that. The e2e test `home.spec.ts` checks today's Home copy and links.
- New pages, new copy, layout changes, new features.
- Anything in `backend/`, `engine/`, `vision/`, `infra/`.
