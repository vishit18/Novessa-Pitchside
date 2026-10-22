import { createContext } from 'react'

/** The colours the pitch canvas draws with. Team kits come from the clubs, not from here. */
export interface PitchPalette {
  apron: number
  grassA: number
  grassB: number
  /** Mowing stripes across the length. 0 draws a flat surface in grassA. */
  stripes: number
  line: number
  lineAlpha: number
  /** Line width in metres. */
  lineWidth: number
  /** Ball trail, carrier ring, pass lines, the followed player. */
  accent: number
  /** Pressing opponents on the analyst layer. */
  press: number
  ball: number
  ink: number
  /** Floodlight falloff across the pitch in landscape. */
  light: boolean
}

/** The broadcast look from docs/07. Every page uses this unless a provider says otherwise. */
export const FLOODLIGHTS: PitchPalette = {
  apron: 0x143a28,
  grassA: 0x1b4a33,
  grassB: 0x1e5237,
  stripes: 14,
  line: 0xe9eef2,
  lineAlpha: 0.7,
  lineWidth: 0.2,
  accent: 0xffb020,
  press: 0xe05cff,
  ball: 0xf6f7f4,
  ink: 0x0d1014,
  light: true,
}

/** Lets a parent (the design lab) repaint the pitch without touching the screens that use it. */
export const PitchPaletteContext = createContext<PitchPalette>(FLOODLIGHTS)
