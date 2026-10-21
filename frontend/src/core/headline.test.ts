import { describe, expect, it } from 'vitest'
import { sentenceCase } from './headline'

describe('sentenceCase', () => {
  it('turns model title case into sentence case, keeping names and xG', () => {
    expect(sentenceCase("Wragg's High xG Leads Goal")).toBe("Wragg's high xG leads goal")
    expect(sentenceCase('Kestrel Bay Controls Possession')).toBe('Kestrel Bay controls possession')
  })

  it('leaves sentence case, one-word headlines and caseless scripts alone', () => {
    expect(sentenceCase('Wragg gives Ashford the lead')).toBe('Wragg gives Ashford the lead')
    expect(sentenceCase('Penalty Scored')).toBe('Penalty scored')
    expect(sentenceCase('Goal')).toBe('Goal')
    expect(sentenceCase('Wragg ने Ashford के लिए गोल किया', 'hi')).toBe(
      'Wragg ने Ashford के लिए गोल किया',
    )
  })
})
