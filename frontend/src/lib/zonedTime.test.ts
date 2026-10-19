import { describe, expect, it } from 'vitest'
import {
  defaultDeparture,
  timeZoneAbbreviation,
  wallClockInZone,
  zonedWallClockToUtc,
} from './zonedTime'

const DENVER = 'America/Denver'

describe('zonedTime', () => {
  it('shows the wall clock of another zone', () => {
    expect(wallClockInZone(new Date('2026-10-20T14:00:00Z'), DENVER)).toBe('2026-10-20T08:00')
  })

  it('converts a daylight-time wall clock to UTC', () => {
    expect(zonedWallClockToUtc('2026-10-20T08:00', DENVER).toISOString()).toBe(
      '2026-10-20T14:00:00.000Z',
    )
  })

  it('converts a standard-time wall clock to UTC', () => {
    expect(zonedWallClockToUtc('2026-11-11T08:00', DENVER).toISOString()).toBe(
      '2026-11-11T15:00:00.000Z',
    )
  })

  it('handles the day daylight saving ends', () => {
    // Clocks fall back at 02:00 on 1 Nov 2026; noon that day is already MST.
    expect(zonedWallClockToUtc('2026-11-01T12:00', DENVER).toISOString()).toBe(
      '2026-11-01T19:00:00.000Z',
    )
  })

  it('round-trips through UTC', () => {
    const wall = '2026-07-04T23:45'
    expect(wallClockInZone(zonedWallClockToUtc(wall, 'America/New_York'), 'America/New_York')).toBe(
      wall,
    )
  })

  it('names the zone abbreviation for the date', () => {
    expect(timeZoneAbbreviation(new Date('2026-10-20T14:00:00Z'), DENVER)).toBe('MDT')
    expect(timeZoneAbbreviation(new Date('2026-12-20T14:00:00Z'), DENVER)).toBe('MST')
  })

  it('rounds the default departure up to the next quarter hour', () => {
    expect(defaultDeparture(new Date('2026-10-20T14:07:30Z'), DENVER)).toBe('2026-10-20T08:15')
    expect(defaultDeparture(new Date('2026-10-20T14:15:00Z'), DENVER)).toBe('2026-10-20T08:15')
  })
})
