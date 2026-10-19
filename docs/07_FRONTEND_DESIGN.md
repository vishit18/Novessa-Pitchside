# Frontend design

UX and presentation is 20% of the score, and the video is judged almost entirely on how the frontend looks. This has to look like a real broadcast product, not a hackathon dashboard.

## Tooling Claude Code must use

1. **frontend-design skill/plugin** (`/plugin install frontend-design@claude-plugins-official`). Load it before building any screen.
2. **Playwright MCP**: after every UI change, open the page, screenshot at **1920×1080** (broadcast) and **390×844** (companion), look at it critically, fix, repeat. Check the Arabic (RTL) layout too. Don't say a screen is done without a screenshot.
3. This doc overrides generic defaults where they conflict.

Stack: React 18 + Vite + TypeScript, Tailwind CSS, Framer Motion (overlay animation), **PixiJS** for the pitch (60 fps with 22 players + ball), Zustand for state, `react-i18next` (with RTL support), Recharts or visx for small charts. WebSocket client with reconnect and buffering.

## Art direction: "floodlights"

The feeling is a night match under floodlights, seen from the gantry. Calm, dark, precise; the data glows.

- **Not** the Premier League look. Avoid their purple and their neon green/cyan combination. No lion, no crown motifs.
- **Base:** graphite / near-black `#0D1014`, raised surfaces `#161B22`, hairlines `#2A313B`.
- **Pitch:** muted deep green with subtle mowing stripes, white lines at ~70% opacity.
- **Accent (the brand):** floodlight amber `#FFB020`.
- **Semantic:** control = ice blue `#5CC8FF`, chaos = signal red `#FF4D4D`, pressure = magenta `#E05CFF`.
- **Team colours** come from the fictional clubs' kits, always shown as small chips, never large floods of colour.
- **Type** (Google Fonts, OFL licence): a condensed display face for numbers and broadcast graphics, e.g. **Barlow Condensed** or **Oswald**; a clean text face for prose, e.g. **Inter** or **IBM Plex Sans**; tabular numerals everywhere numbers change live so they don't jitter. Arabic: **IBM Plex Sans Arabic** or **Noto Sans Arabic**; Hindi: **Noto Sans Devanagari**.
- **Motion:** overlays slide/wipe in like TV graphics (150–250 ms, ease-out), numbers count up, nothing bounces. Respect `prefers-reduced-motion`.
- **Density:** broadcast graphics are sparse. Lower thirds with one headline and one line. The analyst view can be denser but still aligned to a strict grid.

## Screens

1. **Match picker / onboarding**: pick a match, then three quick taps: *How do you watch?* (Analyst, Casual, First match, Audio-described) → *Your club* → *Your player* (optional) → language. Under 15 seconds. Remember it.
2. **Broadcast view** (the hero, 16:9): the 2D tactical feed (optional slight perspective tilt to feel like a camera), score bug top-left, momentum bar, lower thirds, player tags, pitch annotations (pass lines with difficulty, pressure halos). Controls hidden until hover.
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
