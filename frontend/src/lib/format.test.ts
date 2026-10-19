import { describe, expect, it } from 'vitest'
import { formatDuration, formatMiles } from './format'

describe('formatDuration', () => {
  it.each([
    [0, '0 min'],
    [45 * 60, '45 min'],
    [3600, '1 h'],
    [12 * 3600 + 4 * 60 + 20, '12 h 4 min'],
    [59.6 * 60, '1 h'],
  ])('%d s → %s', (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected)
  })
})

describe('formatMiles', () => {
  it('rounds and groups thousands', () => {
    expect(formatMiles(882.3)).toBe('882 mi')
    expect(formatMiles(1145.5)).toBe('1,146 mi')
  })
})
