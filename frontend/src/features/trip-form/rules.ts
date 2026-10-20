// Input rules. These mirror backend/trips/domain/trip_request.py, which is the authoritative check.

export const WEIGHT_MIN_LB = 1_000
export const WEIGHT_MAX_LB = 80_000
export const MAX_DEPARTURE_AHEAD_DAYS = 7
export const RELIABLE_FORECAST_HOURS = 48
export const PAST_DEPARTURE_GRACE_MINUTES = 15
export const MIN_TRIP_MILES = 1

// Load thresholds from the risk rules, shown as a hint under the weight field.
export const WIND_RULE_THRESHOLDS_LB = [30_000, 40_000] as const
