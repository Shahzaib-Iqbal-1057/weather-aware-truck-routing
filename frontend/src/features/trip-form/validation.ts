import type { Place } from '../../api/types'
import { zonedWallClockToUtc } from '../../lib/zonedTime'
import {
  MAX_DEPARTURE_AHEAD_DAYS,
  MIN_TRIP_MILES,
  PAST_DEPARTURE_GRACE_MINUTES,
  RELIABLE_FORECAST_HOURS,
  SPACING_OPTIONS_MI,
  WEIGHT_MAX_LB,
  WEIGHT_MIN_LB,
} from './rules'

export interface TripFormValues {
  origin: Place | null
  destination: Place | null
  /** Wall clock in `departureTimeZone`, "YYYY-MM-DDTHH:MM". */
  departureLocal: string
  departureTimeZone: string
  weightLb: string
  spacingMi: number
}

export type TripFormField = 'origin' | 'destination' | 'departureLocal' | 'weightLb' | 'spacingMi'
export type TripFormErrors = Partial<Record<TripFormField, string>>

const HOUR_MS = 3_600_000

function milesBetween(a: Place, b: Place): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * 3958.8 * Math.asin(Math.sqrt(h))
}

export function validateTripForm(values: TripFormValues, now: Date): TripFormErrors {
  const errors: TripFormErrors = {}

  if (!values.origin) errors.origin = 'Choose an origin from the list.'
  if (!values.destination) errors.destination = 'Choose a destination from the list.'
  if (
    values.origin &&
    values.destination &&
    milesBetween(values.origin, values.destination) < MIN_TRIP_MILES
  ) {
    errors.destination = 'Destination must be a different place from the origin.'
  }

  const departure = parseDeparture(values)
  if (!departure) {
    errors.departureLocal = 'Enter a departure date and time.'
  } else if (departure.getTime() < now.getTime() - PAST_DEPARTURE_GRACE_MINUTES * 60_000) {
    errors.departureLocal = 'Departure time is in the past.'
  } else if (departure.getTime() > now.getTime() + MAX_DEPARTURE_AHEAD_DAYS * 24 * HOUR_MS) {
    errors.departureLocal = `Departure must be within the next ${MAX_DEPARTURE_AHEAD_DAYS} days.`
  }

  const weight = Number(values.weightLb)
  if (values.weightLb.trim() === '' || !Number.isInteger(weight)) {
    errors.weightLb = 'Enter the total weight in whole pounds.'
  } else if (weight < WEIGHT_MIN_LB || weight > WEIGHT_MAX_LB) {
    errors.weightLb = `Weight must be between ${WEIGHT_MIN_LB.toLocaleString('en-US')} and ${WEIGHT_MAX_LB.toLocaleString('en-US')} lb.`
  }

  if (!(SPACING_OPTIONS_MI as readonly number[]).includes(values.spacingMi)) {
    errors.spacingMi = 'Choose a checkpoint spacing.'
  }

  return errors
}

/** Non-blocking notice shown under the departure field. */
export function departureWarning(values: TripFormValues, now: Date): string | null {
  const departure = parseDeparture(values)
  if (departure && departure.getTime() > now.getTime() + RELIABLE_FORECAST_HOURS * HOUR_MS) {
    return `More than ${RELIABLE_FORECAST_HOURS} hours away: the weather forecast is less reliable.`
  }
  return null
}

function parseDeparture(values: TripFormValues): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(values.departureLocal)) return null
  return zonedWallClockToUtc(values.departureLocal, values.departureTimeZone)
}
