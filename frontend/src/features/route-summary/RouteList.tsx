import type { RouteId, RouteResult } from '../../api/types'
import { formatDuration, formatMiles } from '../../lib/format'
import './RouteList.css'

interface RouteListProps {
  routes: RouteResult[]
  notes: string[]
  selectedId: RouteId | null
  onSelect: (id: RouteId) => void
}

export function RouteList({ routes, notes, selectedId, onSelect }: RouteListProps) {
  const fastest = routes[0]?.travel_time_s ?? 0
  return (
    <section className="route-list" aria-label="Route options">
      <h2>Routes</h2>
      <ul>
        {routes.map((route) => {
          const extra = route.travel_time_s - fastest
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
                    {extra === 0 ? (
                      <span className="route-card__tag">Fastest</span>
                    ) : (
                      <span className="route-card__extra">+{formatDuration(extra)}</span>
                    )}
                  </span>
                  <span className="route-card__stats">
                    {formatDuration(route.travel_time_s)} · {formatMiles(route.distance_mi)}
                    {route.traffic_delay_s >= 60 &&
                      ` · ${formatDuration(route.traffic_delay_s)} traffic`}
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
