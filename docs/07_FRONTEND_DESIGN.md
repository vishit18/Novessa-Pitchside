# Frontend design

UX and presentation is 20% of the score, and the video is judged almost entirely on how the frontend looks. This has to look like a real broadcast product, not a hackathon dashboard.

## Tooling Claude Code must use

1. **frontend-design skill/plugin** (`/plugin install frontend-design@claude-plugins-official`). Load it before building any screen.
2. **Playwright MCP**: after every UI change, open the page, screenshot at **1920×1080** (broadcast) and **390×844** (companion), look at it critically, fix, repeat. Check the Arabic (RTL) layout too. Don't say a screen is done without a screenshot.
3. This doc overrides generic defaults where they conflict.

Stack: React 18 + Vite + TypeScript, Tailwind CSS, Framer Motion (overlay animation), **PixiJS** for the pitch (60 fps with 22 players + ball), Zustand for state, `react-i18next` (with RTL support), Recharts or visx for small charts. WebSocket client with reconnect and buffering.

## Art direction: "Matchday broadcast"

A bright matchday afternoon with TV graphics on top. White page, black broadcast plates, a proper green pitch in a black frame like a monitor in the gallery. VJ picked every colour below (look 6 in `/design-lab`); use them exactly.

- **Not** the Premier League look. No purple-and-neon, no lion, no crown, nothing that copies a real broadcaster's graphics package.
- **Page:** white `#FFFFFF`, raised surfaces `#F3F5F2`, hairlines `#D3D9D4`, text `#101418`, muted text `#4F5A54`.
- **Accent:** deep red `#C1121F` on the page (buttons, clocks, the current nav link). Signal yellow `#FFD100` only inside black plates and on the pitch, never on the white page.
- **Plates** (score bug, lower thirds, tags, cards, timeline, menus): solid `#101418`, parallelogram clip `polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)`, no inner highlight, shadow `drop-shadow(0 6px 12px rgb(16 20 24 / .35))`. Inside a plate the tokens flip to light ink: text `#FFFFFF`, muted `#B4BAC2`, hairline `#2C3037`, raised `#1A1D22`, accent `#FFD100`.
- **Pitch:** grass `#2E8B48` / `#349650`, 14 mowing stripes, white lines at 95%, accent `#FFD100`, pressure `#8E24AA`, no light falloff. It sits on a `#101418` stage.
- **Semantic:** control = navy `#1D4ED8`, chaos = amber `#C77700`, pressure = violet `#8E24AA`. On grass, marks in these colours get a thin white outline. Inside black plates they get a white outline or a label next to them. Chaos as text on the page is only for large or bold text (18px+, or 14px+ bold) or as a mark beside ink text.
- **Buttons:** primary is `#C1121F` with white uppercase display text and the parallelogram clip, hover `#A10F1A`. Secondary is a `#101418` outline. Focus ring is 2px `#101418` with a 2px offset.
- **Viewer labels:** first viewer is a yellow `#FFD100` tab with `#101418` text, second viewer a red `#C1121F` tab with white text, both sitting on top of the pane frame.
- **Team colours** come from the fictional clubs' kits, always shown as small chips, never large floods of colour.
- **Type** (OFL licence): **Big Shoulders Display** 800 for numbers and broadcast graphics, uppercase for headlines; **Figtree** 400/600 for prose; tabular numerals everywhere numbers change live so they don't jitter. Arabic: **IBM Plex Sans Arabic**; Hindi: **Noto Sans Devanagari**. Uppercase does nothing in Arabic, so hierarchy never relies on caps alone.
- **Motion:** plates and tags wipe in left to right in 180 ms, ease-out. Numbers count up, nothing bounces. `prefers-reduced-motion` turns every entrance into a plain fade.
- **Density:** broadcast graphics are sparse. Lower thirds with one headline and one line. The analyst view can be denser but still aligned to a strict grid. Tight spacing, 2px radius.

As shipped (22 Oct), details the values above don't cover:

- The black stage (`.stage-bg`) sits only behind the pitch and the real-footage video. Every other page, Companion, Control room, Recap and Real footage included, is on the white page.
- Plates and the stage flip all the tokens to light ink, `--color-ink` included (to `#101418`), so an accent button inside a plate is yellow with dark text.
- Skewed controls (primary buttons, plate chips) clip an outside focus ring, so theirs sits 5px inside, in the control's own text colour.
- A colour strip on a plate's edge (`.plate-edge`) is skewed to run parallel to it.
- Pressure halos on the pitch get a thin white edge (`outline` in the `MATCHDAY` pitch palette).
- Jersey numbers on the pitch canvas and the real-footage labels still draw in Barlow Condensed, as in the `/design-lab` reference.

## Screens

Every screen except the full-screen broadcast carries the same header: wordmark (home) and one link per screen, the current one underlined in amber. The broadcast has a single Menu button in its corner instead, so nothing sits on the football.

0. **Home** (`/`): says the problem in one line ("Millions watch the same match. They all get the same broadcast."), shows the answer on one real goal told three ways (Analyst/English, Casual/Spanish, First match/Hindi, live agent text with a captured fallback), the six steps a moment goes through, and every way in labelled by who it is for. A newcomer should know what this is without clicking anything.
1. **Match picker / onboarding** (`/start`): pick a match, then three quick taps: *How do you watch?* (Analyst, Casual, First match, Audio-described) → *Your club* → *Your player* (optional) → language. Under 15 seconds. Remember it.
2. **Broadcast view** (the hero, 16:9): the 2D tactical feed (optional slight perspective tilt to feel like a camera), score bug top-left, momentum bar, lower thirds, player tags, pitch annotations (pass lines with difficulty, pressure halos). Controls hidden until hover, always shown while paused. The controls are a timeline: play, skip 30 s, drag to any minute (one seek on release), speed, and markers for goals and cards. Markers only cover what the viewer has already watched unless they switch on Key moments, because the full set gives away the result.
3. **Split view: "Same match. Your story."** Two personas side by side on the same moment: e.g. Analyst/English vs Casual/Spanish. This is the money shot for the video; make it beautiful.
4. **Player focus mode**: pitch follows one player, their live card (speed, distance, passes, difficulty, heatmap building over time), everything framed around them.
5. **One-number mode**: viewer picks one metric; the UI reorganises around it with a big live number and its story.
6. **Companion (mobile, 390 wide)**: the streaming/second-screen experience. Vertical feed of moments, tap to expand the "why", audio commentary toggle, "what did I miss?" button.
7. **Control Room** (producer view): live agent graph with each agent lighting up as it works, the moment queue with Producer decisions, Verifier ticks/crosses, latency p50/p95, cost so far, circuit-breaker states, and the **chaos switch**. This is where judges *see* the backend and the multi-agent system.
8. **Recap page**: half/full-time recap per persona and language, key moments timeline, highlight script, share button.
9. **Real footage mode**: video player with overlays tracking real players.

## Must-haves

- Works at 1920×1080 and 1280×720 for broadcast; 390×844 for companion.
- Arabic is right-to-left and looks right.
- Keyboard accessible, visible focus, WCAG AA contrast, captions for voice.
- Loading, empty and error states designed, not default.
- A subtle "Novessa Pitchside" wordmark (text-based, original), never a logo resembling any real league or club.
- No placeholder lorem ipsum anywhere by recording day.
