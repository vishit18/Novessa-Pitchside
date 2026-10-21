import { CLUBS, PLAYERS } from '@/data/league'

/** Words that keep their capitals: every club and player name in the league, plus xG. */
const PROPER = new Set<string>(
  [
    ...Object.values(CLUBS).flatMap((c) => c.name.split(' ')),
    ...Object.values(PLAYERS).flatMap((p) => p.name.split(' ')),
    'xG',
    'FC',
  ].filter(Boolean),
)

const CASED = /^(en|es|fr|pt)$/

/**
 * Models like Title Case ("Wragg's High xG Leads Goal"); broadcast graphics use sentence case.
 * Only rewrites a headline where at least two ordinary words all start with a capital, so a
 * headline that is already sentence case, or a language without case, is left alone.
 */
export function sentenceCase(text: string, lang = 'en'): string {
  if (!CASED.test(lang)) return text
  const words = text.split(' ')
  const letters = words.filter((w) => /^\p{L}/u.test(w) && !PROPER.has(w))
  if (letters.length < 2 || !letters.every((w) => /^\p{Lu}/u.test(w))) return text
  return words
    .map((w, i) => {
      const bare = w.replace(/[’']s$|[^\p{L}]/gu, '')
      if (i === 0 || PROPER.has(bare) || /^\p{Lu}{2,}$/u.test(bare)) return w
      return w.toLowerCase()
    })
    .join(' ')
}
