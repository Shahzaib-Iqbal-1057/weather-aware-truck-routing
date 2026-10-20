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
  /** Freight only; the empty truck is assumed to weigh 35,000 lb. */
  cargo_weight_lb: number
}

export interface Trip {
  origin: Place
  destination: Place
  departure_local: string
  departure_utc: string
  departure_timezone: string
  departure_timezone_abbr: string
  cargo_weight_lb: number
  spacing_mi: number
}

export type RouteId = 'A' | 'B' | 'C'

/** Forecast for the hour the truck reaches a checkpoint. */
export interface CheckpointWeather {
  /** End of the forecast hour; rain and snow are totals for the hour before it. */
  forecast_hour_utc: string
  /** Sustained wind, used by the risk rules. */
  wind_mph: number
  gust_mph: number | null
  /** Rain plus showers. */
  rain_in_per_hr: number
  snow_in_per_hr: number
  temperature_f: number | null
  conditions: string | null
}

export interface Checkpoint {
  /** [lon, lat] */
  position: [number, number]
  mile: number
  eta_utc: string
  /** null when no forecast is available for this place and hour. */
  weather: CheckpointWeather | null
}

export interface RestStop {
  /** "break" is 30 minutes after 8 h of driving; "rest" is 10 hours after 11 h. */
  kind: 'break' | 'rest'
  /** [lon, lat] */
  position: [number, number]
  mile: number
  starts_utc: string
  ends_utc: string
}

export interface RouteResult {
  id: RouteId
  distance_mi: number
  driving_time_s: number
  /** Door to door, including rest stops. */
  trip_time_s: number
  arrival_utc: string
  /** Simplified display line, [lon, lat] pairs. */
  geometry: [number, number][]
  /** [lon, lat] for the map label, on road no other route uses. */
  label_position: [number, number]
  /** Every 10 miles from the start, plus the destination. */
  checkpoints: Checkpoint[]
  rest_stops: RestStop[]
}

export interface TripPlanResponse {
  trip: Trip
  /** Fastest first (earliest arrival). */
  routes: RouteResult[]
  /** False when the weather service failed; routes are still shown. */
  weather_available: boolean
  notes: string[]
  warnings: string[]
}

/** DRF validation error body: field name → messages (nested objects for nested serializers). */
export type ValidationErrorBody = Record<string, string[] | Record<string, string[]>>
