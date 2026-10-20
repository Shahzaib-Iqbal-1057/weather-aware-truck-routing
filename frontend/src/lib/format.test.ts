import { describe, expect, it } from 'vitest'
import type { CheckpointWeather } from '../api/types'
import { formatClock, formatDuration, formatMiles, formatWeather } from './format'

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

describe('formatClock', () => {
  it('shows the time on the given clock with its zone', () => {
    expect(formatClock('2026-10-21T11:50:00Z', 'America/Chicago')).toBe('Wed 6:50 AM CDT')
    expect(formatClock('2026-10-21T11:50:00Z', 'America/Denver')).toBe('Wed 5:50 AM MDT')
  })
})

describe('formatWeather', () => {
  const calm: CheckpointWeather = {
    forecast_hour_utc: '2026-10-20T15:00:00Z',
    wind_mph: 7.2,
    gust_mph: 13.6,
    rain_in_per_hr: 0,
    snow_in_per_hr: 0,
    temperature_f: 56,
    conditions: 'Clear',
  }

  it('summarises calm weather without zero rain or snow', () => {
    expect(formatWeather(calm)).toBe('Clear, 56°F · wind 7 mph (gusts 14)')
  })

  it('includes rain and snow intensity when present', () => {
    expect(
      formatWeather({
        ...calm,
        conditions: 'Snow',
        temperature_f: 28,
        rain_in_per_hr: 0.04,
        snow_in_per_hr: 0.8,
      }),
    ).toBe('Snow, 28°F · wind 7 mph (gusts 14) · rain 0.04 in/hr · snow 0.80 in/hr')
  })

  it('copes with missing optional values', () => {
    expect(formatWeather({ ...calm, conditions: null, temperature_f: null, gust_mph: null })).toBe(
      'wind 7 mph',
    )
  })

  it('says so when there is no forecast', () => {
    expect(formatWeather(null)).toBe('Weather unavailable')
  })
})
