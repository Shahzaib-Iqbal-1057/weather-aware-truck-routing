// Input rules. These mirror backend/trips/domain/trip_request.py, which is the authoritative check.

// The brief's "load weight" is the cargo. Max = 80,000 lb legal gross − 35,000 lb empty truck.
export const CARGO_MIN_LB = 0
export const CARGO_MAX_LB = 45_000
export const EMPTY_TRUCK_LB = 35_000
export const LEGAL_GROSS_LB = 80_000
export const MAX_DEPARTURE_AHEAD_DAYS = 7
export const RELIABLE_FORECAST_HOURS = 48
export const PAST_DEPARTURE_GRACE_MINUTES = 15
export const MIN_TRIP_MILES = 1
