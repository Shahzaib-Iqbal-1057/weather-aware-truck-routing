import { describe, expect, it } from 'vitest'
import { RISK_LEVELS, riskStyle } from './risk'

describe('risk levels', () => {
  it('are ordered from least to most severe, then unknown', () => {
    expect(RISK_LEVELS.map((level) => level.label)).toEqual([
      'Low',
      'Moderate',
      'High',
      'Severe',
      'No Travel',
      'Unknown',
    ])
  })

  it('each have a distinct colour', () => {
    expect(new Set(RISK_LEVELS.map((level) => level.color)).size).toBe(RISK_LEVELS.length)
  })

  it('are looked up by the API key', () => {
    expect(riskStyle('no_travel').label).toBe('No Travel')
  })
})
