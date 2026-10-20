import { describe, expect, it } from 'vitest'
import type { Place } from '../../api/types'
import { departureWarning, validateTripForm, type TripFormValues } from './validation'

const DENVER: Place = {
  label: 'Denver, CO',
  lat: 39.7392,
  lon: -104.9903,
  kind: 'city',
  timezone: 'America/Denver',
}
const DALLAS: Place = {
  label: 'Dallas, TX',
  lat: 32.7767,
  lon: -96.797,
  kind: 'city',
  timezone: 'America/Chicago',
}
const NOW = new Date('2026-10-19T12:00:00Z') // 06:00 in Denver

function values(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    origin: DENVER,
    destination: DALLAS,
    departureLocal: '2026-10-20T08:00',
    departureTimeZone: 'America/Denver',
    weightLb: '40000',
    ...overrides,
  }
}

describe('validateTripForm', () => {
  it('accepts a complete, valid trip', () => {
    expect(validateTripForm(values(), NOW)).toEqual({})
  })

  it('requires origin and destination to be picked from the list', () => {
    const errors = validateTripForm(values({ origin: null, destination: null }), NOW)
    expect(errors.origin).toBeDefined()
    expect(errors.destination).toBeDefined()
  })

  it('rejects the same place as origin and destination', () => {
    expect(validateTripForm(values({ destination: DENVER }), NOW).destination).toMatch(/different/)
  })

  it.each(['1000', '80000'])('accepts weight %s', (weightLb) => {
    expect(validateTripForm(values({ weightLb }), NOW).weightLb).toBeUndefined()
  })

  it.each(['', '999', '80001', '40000.5', 'abc'])('rejects weight "%s"', (weightLb) => {
    expect(validateTripForm(values({ weightLb }), NOW).weightLb).toBeDefined()
  })

  it('reads the departure in the origin time zone', () => {
    // 05:50 Denver = 10 minutes ago, inside the grace period.
    expect(validateTripForm(values({ departureLocal: '2026-10-19T05:50' }), NOW)).toEqual({})
    // 05:50 New York would be hours in the past.
    const eastern = values({
      departureLocal: '2026-10-19T05:50',
      departureTimeZone: 'America/New_York',
    })
    expect(validateTripForm(eastern, NOW).departureLocal).toMatch(/past/)
  })

  it('rejects departures more than 7 days ahead', () => {
    expect(
      validateTripForm(values({ departureLocal: '2026-10-27T08:00' }), NOW).departureLocal,
    ).toMatch(/7 days/)
  })

  it('requires a departure time', () => {
    expect(validateTripForm(values({ departureLocal: '' }), NOW).departureLocal).toBeDefined()
  })
})

describe('departureWarning', () => {
  it('warns only beyond 48 hours', () => {
    expect(departureWarning(values({ departureLocal: '2026-10-21T05:00' }), NOW)).toBeNull()
    expect(departureWarning(values({ departureLocal: '2026-10-22T08:00' }), NOW)).toMatch(
      /48 hours/,
    )
  })
})
