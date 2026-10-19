/** Who is watching and how. Sent to the gateway as WebSocket query params (docs/05 Transport). */

/** Same values as backend/app/overlay.py Persona. */
export type Persona = 'analyst' | 'casual' | 'kids' | 'accessibility'
export type Lang = 'en' | 'es' | 'ar'

export interface ViewerProfile {
  viewerId: string
  persona: Persona
  lang: Lang
  /** Club code the viewer supports, if any. */
  club: string | null
  /** Player id the viewer follows, if any. Player-focus mode. */
  player: string | null
  /** One-number mode: the single metric the viewer picked, if any. */
  metric: string | null
}

export const PERSONAS: { id: Persona; label: string; hint: string }[] = [
  { id: 'analyst', label: 'Analyst', hint: 'Every number, and why it matters' },
  { id: 'casual', label: 'Casual', hint: 'The story, without the spreadsheet' },
  { id: 'kids', label: 'First match', hint: 'What is going on, in plain words' },
  { id: 'accessibility', label: 'Audio-described', hint: 'Spoken commentary with captions' },
]

export const LANGS: { id: Lang; label: string }[] = [
  { id: 'en', label: 'English' },
  { id: 'es', label: 'Español' },
  { id: 'ar', label: 'العربية' },
]

export const isRtl = (lang: Lang) => lang === 'ar'

const KEY = 'pitchside.profile.v1'

function newViewerId(): string {
  const r = Math.random().toString(36).slice(2, 10)
  return `viewer-${r}`
}

export function defaultProfile(over: Partial<ViewerProfile> = {}): ViewerProfile {
  return {
    viewerId: newViewerId(),
    persona: 'casual',
    lang: 'en',
    club: null,
    player: null,
    metric: null,
    ...over,
  }
}

/** The saved profile, or null on first visit (or when storage is blocked). */
export function loadProfile(): ViewerProfile | null {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return null
    const p = JSON.parse(raw) as Partial<ViewerProfile>
    if (!p.persona || !p.lang) return null
    return defaultProfile(p)
  } catch {
    return null
  }
}

export function saveProfile(p: ViewerProfile): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(p))
  } catch {
    // Private mode or blocked storage: the profile still works for this visit.
  }
}
