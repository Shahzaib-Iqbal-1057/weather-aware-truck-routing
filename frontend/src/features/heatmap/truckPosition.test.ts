import { describe, expect, it } from 'vitest'
import { makeRoute } from '../../test/fixtures'
import { truckPositionAt } from './truckPosition'

const at = (iso: string) => Date.parse(iso)

const ROUTE = makeRoute({
  checkpoints: [
    {
      position: [0, 0],
      mile: 0,
      eta_utc: '2026-10-21T10:00:00Z',
      weather: null,
      risk: { level: 'low', reasons: [] },
    },
    {
      position: [10, 0],
      mile: 10,
      eta_utc: '2026-10-21T11:00:00Z',
      weather: null,
      risk: { level: 'low', reasons: [] },
    },
    {
      position: [20, 0],
      mile: 20,
      eta_utc: '2026-10-21T22:00:00Z',
      weather: null,
      risk: { level: 'low', reasons: [] },
    },
  ],
  // Parked at x=15 from 12:00 to 21:00, between the second and third checkpoints.
  rest_stops: [
    {
      kind: 'rest',
      position: [15, 0],
      mile: 15,
      starts_utc: '2026-10-21T12:00:00Z',
      ends_utc: '2026-10-21T21:00:00Z',
    },
  ],
})

describe('truckPositionAt', () => {
  it('is at the start before departure and at the end after arrival', () => {
    expect(truckPositionAt(ROUTE, at('2026-10-21T08:00:00Z'))).toEqual([0, 0])
    expect(truckPositionAt(ROUTE, at('2026-10-22T08:00:00Z'))).toEqual([20, 0])
  })

  it('moves between checkpoints in proportion to time', () => {
    expect(truckPositionAt(ROUTE, at('2026-10-21T10:30:00Z'))).toEqual([5, 0])
  })

  it('stays parked for the whole rest stop', () => {
    expect(truckPositionAt(ROUTE, at('2026-10-21T12:00:00Z'))).toEqual([15, 0])
    expect(truckPositionAt(ROUTE, at('2026-10-21T16:30:00Z'))).toEqual([15, 0])
    expect(truckPositionAt(ROUTE, at('2026-10-21T21:00:00Z'))).toEqual([15, 0])
  })

  it('is null for a route without checkpoints', () => {
    expect(truckPositionAt(makeRoute(), at('2026-10-21T10:00:00Z'))).toBeNull()
  })
})
