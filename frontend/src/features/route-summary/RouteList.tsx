import type { Recommendation, RouteId, RouteResult } from '../../api/types'
import { formatClock, formatDuration, formatMiles } from '../../lib/format'
import './RouteList.css'
import { riskSummary } from './riskSummary'

interface RouteListProps {
  routes: RouteResult[]
  notes: string[]
  selectedId: RouteId | null
  onSelect: (id: RouteId) => void
  /** Times are shown on the departure city's clock. */
  timeZone: string
  /** Short destination name, e.g. "Atlanta". */
  destinationName: string
  recommendation: Recommendation
}

// A 10-hour rest this close to the destination makes the door-to-door time look odd, so say why.
const NEAR_DESTINATION_MI = 25

function restNearDestinationNote(route: RouteResult, destinationName: string): string | null {
  const rest = route.rest_stops.find(
    (stop) => stop.kind === 'rest' && route.distance_mi - stop.mile <= NEAR_DESTINATION_MI,
  )
  if (!rest) return null
  const milesLeft = Math.max(1, Math.round(route.distance_mi - rest.mile))
  const length = formatDuration((Date.parse(rest.ends_utc) - Date.parse(rest.starts_utc)) / 1000)
  return `Includes a ${length} rest ${milesLeft} mi before ${destinationName}: the 11-hour driving limit runs out first.`
}

export function RouteList({
  routes,
  notes,
  selectedId,
  onSelect,
  timeZone,
  destinationName,
  recommendation,
}: RouteListProps) {
  const earliest = routes[0]?.trip_time_s ?? 0
  return (
    <section className="route-list" aria-label="Route options">
      <h2>Routes</h2>
      <p
        className={`route-list__recommendation${recommendation.route_id ? '' : ' route-list__recommendation--none'}`}
        role="status"
      >
        <strong>
          {recommendation.route_id
            ? `Recommended: Route ${recommendation.route_id}`
            : 'No route recommended'}
        </strong>
        <span>{recommendation.reason}</span>
      </p>
      <ul>
        {routes.map((route) => {
          const later = route.trip_time_s - earliest
          const resting = route.trip_time_s - route.driving_time_s
          const restNote = restNearDestinationNote(route, destinationName)
          return (
            <li key={route.id}>
              <button
                type="button"
                className="route-card"
                aria-pressed={route.id === selectedId}
                onClick={() => onSelect(route.id)}
              >
                <span className="route-card__badge" aria-hidden="true">
                  {route.id}
                </span>
                <span className="route-card__body">
                  <span className="route-card__title">
                    Route {route.id}
                    {route.id === recommendation.route_id && (
                      <span className="route-card__tag route-card__tag--recommended">
                        Recommended
                      </span>
                    )}
                    {later === 0 ? (
                      <span className="route-card__tag">Fastest</span>
                    ) : (
                      <span className="route-card__extra">+{formatDuration(later)}</span>
                    )}
                  </span>
                  <span className="route-card__arrival">
                    Arrives {formatClock(route.arrival_utc, timeZone)}
                  </span>
                  <span className="route-card__stats">
                    {formatDuration(route.driving_time_s)} driving
                    {resting > 0 && ` + ${formatDuration(resting)} rest`} ·{' '}
                    {formatMiles(route.distance_mi)}
                  </span>
                  <span className="route-card__risk">{riskSummary(route)}</span>
                  {route.totals.no_travel_mi > 0 && (
                    <span className="route-card__no-travel">
                      No Travel conditions on {Math.round(route.totals.no_travel_mi)} mi
                    </span>
                  )}
                  {restNote && <span className="route-card__note">{restNote}</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {notes.map((note) => (
        <p key={note} className="route-list__note">
          {note}
        </p>
      ))}
    </section>
  )
}
