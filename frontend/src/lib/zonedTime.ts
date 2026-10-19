// Helpers for wall-clock times ("YYYY-MM-DDTHH:MM") in a specific IANA time zone.
// The browser only knows its own zone, but departure times are entered in the origin's zone.

const MINUTE_MS = 60_000

function partsInZone(date: Date, timeZone: string): Record<string, number> {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  const parts: Record<string, number> = {}
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== 'literal') parts[part.type] = Number(part.value)
  }
  return parts
}

const pad = (value: number) => String(value).padStart(2, '0')

/** The wall-clock time a clock in `timeZone` shows at `date`. */
export function wallClockInZone(date: Date, timeZone: string): string {
  const p = partsInZone(date, timeZone)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`
}

function wallClockAsUtcMs(wallClock: string): number {
  return Date.parse(`${wallClock}:00Z`)
}

/** The instant at which a clock in `timeZone` shows `wallClock`. */
export function zonedWallClockToUtc(wallClock: string, timeZone: string): Date {
  const target = wallClockAsUtcMs(wallClock)
  // First guess treats the wall clock as UTC, then correct by the zone's offset.
  // A second pass handles guesses that land on the other side of a DST change.
  let instant = target
  for (let i = 0; i < 2; i++) {
    const offset = wallClockAsUtcMs(wallClockInZone(new Date(instant), timeZone)) - instant
    instant = target - offset
  }
  return new Date(instant)
}

/** Short zone name at an instant, e.g. "MDT" or "MST". */
export function timeZoneAbbreviation(date: Date, timeZone: string): string {
  const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'short' })
    .formatToParts(date)
    .find((p) => p.type === 'timeZoneName')
  return part?.value ?? timeZone
}

/** "Now", rounded up to the next quarter hour, as a wall clock in `timeZone`. */
export function defaultDeparture(now: Date, timeZone: string): string {
  const step = 15 * MINUTE_MS
  return wallClockInZone(new Date(Math.ceil(now.getTime() / step) * step), timeZone)
}

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}
