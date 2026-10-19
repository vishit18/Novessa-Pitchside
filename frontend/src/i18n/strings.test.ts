import { describe, expect, it } from 'vitest'
import { outcomeLabel, STRINGS, translate } from './strings'

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('strings', () => {
  it('every language has every key, with the same placeholders as English', () => {
    for (const [lang, table] of Object.entries(STRINGS)) {
      for (const [key, en] of Object.entries(STRINGS.en)) {
        const v = table[key as keyof typeof STRINGS.en]
        expect(v, `${lang}.${key}`).toBeTruthy()
        expect(placeholders(v), `${lang}.${key}`).toEqual(placeholders(en))
      }
    }
  })

  it('fills placeholders', () => {
    expect(translate('en', 'passDone', { m: 32 })).toBe('32 m, completed')
    expect(translate('es', 'shotBy', { name: 'Ana' })).toBe('Disparo de Ana')
  })

  it('translates known shot outcomes and passes unknown ones through readably', () => {
    expect(outcomeLabel('es', 'saved')).toBe('parada')
    expect(outcomeLabel('en', 'hit_post')).toBe('hit post')
  })
})
