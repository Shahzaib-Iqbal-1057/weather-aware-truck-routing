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
    cargoWeightLb: '30000',
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

  it.each(['0', '30000', '45000'])('accepts cargo weight %s', (cargoWeightLb) => {
    expect(validateTripForm(values({ cargoWeightLb }), NOW).cargoWeightLb).toBeUndefined()
  })

  it.each(['', '-1', '45001', '80000', '30000.5', 'abc'])(
    'rejects cargo weight "%s"',
    (cargoWeightLb) => {
      expect(validateTripForm(values({ cargoWeightLb }), NOW).cargoWeightLb).toBeDefined()
    },
  )

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

  it('rejects a departure in the daylight-saving gap', () => {
    // 8 Mar 2026 in Denver: clocks jump from 2:00 to 3:00, so 2:30 never happens.
    const now = new Date('2026-03-07T12:00:00Z')
    expect(
      validateTripForm(values({ departureLocal: '2026-03-08T02:30' }), now).departureLocal,
    ).toMatch(/daylight saving/)
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
