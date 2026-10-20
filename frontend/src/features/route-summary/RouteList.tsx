import type { RouteId, RouteResult } from '../../api/types'
import { formatClock, formatDuration, formatMiles } from '../../lib/format'
import './RouteList.css'

interface RouteListProps {
  routes: RouteResult[]
  notes: string[]
  selectedId: RouteId | null
  onSelect: (id: RouteId) => void
  /** Times are shown on the departure city's clock. */
  timeZone: string
}

export function RouteList({ routes, notes, selectedId, onSelect, timeZone }: RouteListProps) {
  const earliest = routes[0]?.trip_time_s ?? 0
  return (
    <section className="route-list" aria-label="Route options">
      <h2>Routes</h2>
      <ul>
        {routes.map((route) => {
          const later = route.trip_time_s - earliest
          const resting = route.trip_time_s - route.driving_time_s
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
