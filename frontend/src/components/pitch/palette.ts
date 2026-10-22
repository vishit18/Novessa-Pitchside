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
  /** A thin edge drawn around coloured marks so they separate from the grass. None if unset. */
  outline?: number
}

/** The pitch before look 6. The design lab still shows it as the Floodlights baseline. */
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

/** The broadcast look from docs/07 (Matchday broadcast). Every page uses this unless a provider says otherwise. */
export const MATCHDAY: PitchPalette = {
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
  outline: 0xffffff,
}

/** Lets a parent (the design lab) repaint the pitch without touching the screens that use it. */
export const PitchPaletteContext = createContext<PitchPalette>(MATCHDAY)
