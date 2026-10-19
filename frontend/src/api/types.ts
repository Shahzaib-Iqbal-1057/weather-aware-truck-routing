// Response shapes returned by the Django API (keep in sync with backend serializers).

export interface HealthResponse {
  status: 'ok'
}

export type PlaceKind = 'city' | 'address' | 'place'

export interface Place {
  label: string
  lat: number
  lon: number
  kind: PlaceKind
  timezone: string | null
}

export interface GeocodeResponse {
  results: Place[]
}

export interface TripPlanRequest {
  origin: Pick<Place, 'label' | 'lat' | 'lon' | 'kind'>
  destination: Pick<Place, 'label' | 'lat' | 'lon' | 'kind'>
  /** Wall-clock time in the origin's time zone, "YYYY-MM-DDTHH:MM". */
  departure_local: string
  weight_lb: number
  spacing_mi: number
}

export interface Trip {
  origin: Place
  destination: Place
  departure_local: string
  departure_utc: string
  departure_timezone: string
  departure_timezone_abbr: string
  weight_lb: number
  spacing_mi: number
}

export type RouteId = 'A' | 'B' | 'C'

export interface RouteResult {
  id: RouteId
  distance_mi: number
  travel_time_s: number
  traffic_delay_s: number
  /** Simplified display line, [lon, lat] pairs. */
  geometry: [number, number][]
}

export interface TripPlanResponse {
  trip: Trip
  /** Ordered by travel time; the first is the fastest. */
  routes: RouteResult[]
  notes: string[]
  warnings: string[]
}

/** DRF validation error body: field name → messages (nested objects for nested serializers). */
export type ValidationErrorBody = Record<string, string[] | Record<string, string[]>>
