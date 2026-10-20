import type { RouteResult } from '../api/types'

/** A route as the API returns it, with only the fields a test cares about overridden. */
export function makeRoute(overrides: Partial<RouteResult> = {}): RouteResult {
  return {
    id: 'A',
    distance_mi: 100,
    driving_time_s: 2 * 3600,
    trip_time_s: 2 * 3600,
    arrival_utc: '2026-10-20T15:00:00Z',
    totals: { severe_mi: 0, high_mi: 0, no_travel_mi: 0, unknown_mi: 0, average_risk: 0 },
    geometry: [],
    label_position: [0, 0],
    checkpoints: [],
    rest_stops: [],
    ...overrides,
  }
}
