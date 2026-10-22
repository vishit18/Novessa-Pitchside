/*
 * Five looks for the same first-impression screen. Same data, same components, different skin.
 * Colours and fonts live in lab.css under `.lab-<id>`; that file also re-points the app's own
 * tokens (--color-ink, --color-amber, --font-display...) so the real score bug, lower thirds and
 * tags pick the look up without a line of their code changing. The pitch canvas gets its palette
 * here, through PitchPaletteContext.
 *
 * 1. Matchday bright
 *    Type: Bricolage Grotesque 800 (headlines), Figtree (text). Colour: chalk white #F3F6F4,
 *    pitch-black green text #0F1D17, scarf orange #FF5B14, grass #1C8C4E. Spacing: tight, app-like,
 *    14px radius. Motion: panes rise 16px in 220ms, 60ms stagger.
 * 2. Sports magazine
 *    Type: Fraunces 600 (headlines), Libre Franklin (text). Colour: paper #EFE7D6, ink #1E1B16,
 *    print red #B3261E, bottle green #1F4D3A. Spacing: wide margins, hairline rules, no radius.
 *    Motion: a slow fade and 12px drift, 300ms, no wipes.
 * 3. Broadcast graphics
 *    Type: Big Shoulders Display 800 caps (headlines), Archivo (text). Colour: black #07080A,
 *    white, signal yellow #FFD100, red #E4002B. Spacing: full-bleed panes, 2px gutters, skewed
 *    plates. Motion: hard left-to-right wipes, 180ms; tags wipe in too.
 * 4. Tactics board
 *    Type: Caveat Brush (headlines and chalk notes), Atkinson Hyperlegible (text and numbers).
 *    Colour: slate #1D2622, chalk #ECEAE2, yellow chalk #F4D35E, pink chalk #F28FA0. Spacing:
 *    loose, dashed chalk frames. Motion: arrows draw themselves on, 280ms each.
 * 5. Floodlights (baseline)
 *    Type: Barlow Condensed, Inter. Colour: graphite #0D1014, amber #FFB020. Spacing and motion
 *    as the app ships today (docs/07): plates wipe in 150-250ms.
 * 6. Matchday broadcast (1 + 3). VJ's pick for the whole app; colours chosen by him.
 *    Matchday's daylight with broadcast graphics on top. Type: Big Shoulders Display 800 caps
 *    (headlines), Figtree (text). Colour: white page #FFFFFF, ink #101418, deep red #C1121F
 *    (buttons, clocks on the page, second viewer tab), signal yellow #FFD100 (inside black plates,
 *    first viewer tab), grass #2E8B48/#349650, stats navy #1D4ED8 / amber #C77700 / violet #8E24AA.
 *    Black skewed TV plates sit on the bright page; each feed gets a hard black frame with its
 *    viewer tab clipped to the top, so the two screens read as two monitors. No pills, no orange.
 *    Spacing: tight, 2px radius. Motion: broadcast wipes, 180ms.
 */
import { FLOODLIGHTS, type PitchPalette } from '@/components/pitch/palette'

export type DirectionId =
  'matchday' | 'magazine' | 'broadcast' | 'tactics' | 'floodlights' | 'blend'

export interface Direction {
  id: DirectionId
  name: string
  /** How the screen enters. All under 300ms; reduced motion turns them into plain fades. */
  motion: 'rise' | 'drift' | 'wipe' | 'chalk' | 'plate'
  pitch: PitchPalette
}

export const DIRECTIONS: Direction[] = [
  {
    id: 'matchday',
    name: 'Matchday bright',
    motion: 'rise',
    pitch: {
      apron: 0x2f8a45,
      grassA: 0x3a9e4f,
      grassB: 0x43a858,
      stripes: 10,
      line: 0xffffff,
      lineAlpha: 0.92,
      lineWidth: 0.24,
      accent: 0xff5b14,
      press: 0xc2006b,
      ball: 0xffffff,
      ink: 0x0f1d17,
      light: false,
    },
  },
  {
    id: 'magazine',
    name: 'Sports magazine',
    motion: 'drift',
    pitch: {
      apron: 0x5a7350,
      grassA: 0x6b8a5a,
      grassB: 0x728f61,
      stripes: 7,
      line: 0xf6efe0,
      lineAlpha: 0.85,
      lineWidth: 0.22,
      accent: 0xb3261e,
      press: 0x1f4d3a,
      ball: 0xfbf7ee,
      ink: 0x1e1b16,
      light: false,
    },
  },
  {
    id: 'broadcast',
    name: 'Broadcast graphics',
    motion: 'wipe',
    pitch: {
      apron: 0x0c2416,
      grassA: 0x124a27,
      grassB: 0x16572e,
      stripes: 18,
      line: 0xffffff,
      lineAlpha: 0.95,
      lineWidth: 0.26,
      accent: 0xffd100,
      press: 0xe4002b,
      ball: 0xffffff,
      ink: 0x07080a,
      light: true,
    },
  },
  {
    id: 'tactics',
    name: 'Tactics board',
    motion: 'chalk',
    pitch: {
      apron: 0x1d2622,
      grassA: 0x24302a,
      grassB: 0x24302a,
      stripes: 0,
      line: 0xeceae2,
      lineAlpha: 0.6,
      lineWidth: 0.3,
      accent: 0xf4d35e,
      press: 0xf28fa0,
      ball: 0xffffff,
      ink: 0x1d2622,
      light: false,
    },
  },
  { id: 'floodlights', name: 'Floodlights', motion: 'plate', pitch: FLOODLIGHTS },
  {
    id: 'blend',
    name: 'Matchday broadcast',
    motion: 'wipe',
    pitch: {
      apron: 0x277a3e,
      grassA: 0x2e8b48,
      grassB: 0x349650,
      stripes: 14,
      line: 0xffffff,
      lineAlpha: 0.95,
      lineWidth: 0.24,
      accent: 0xffd100,
      press: 0x8e24aa,
      ball: 0xffffff,
      ink: 0x101418,
      light: false,
    },
  },
]
