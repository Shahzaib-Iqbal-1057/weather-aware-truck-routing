import { useState } from 'react'
import type { RouteResult } from '../../api/types'
import { formatClock, formatDuration, formatWeather } from '../../lib/format'
import { riskStyle } from '../../lib/risk'
import './CheckpointTable.css'

interface CheckpointTableProps {
  route: RouteResult
  /** Times are shown on the departure city's clock. */
  timeZone: string
}

type Row =
  | { kind: 'checkpoint'; mile: number; index: number }
  | { kind: 'stop'; mile: number; index: number }

/**
 * Everything the map's checkpoint dots and rest-stop markers show, as a table: readable without
 * a mouse or a screen, and easy to scan for the risky miles.
 */
export function CheckpointTable({ route, timeZone }: CheckpointTableProps) {
  const [riskyOnly, setRiskyOnly] = useState(false)
  const rows: Row[] = [
    ...route.checkpoints.map((c, index) => ({ kind: 'checkpoint' as const, mile: c.mile, index })),
    ...route.rest_stops.map((s, index) => ({ kind: 'stop' as const, mile: s.mile, index })),
  ].sort((a, b) => a.mile - b.mile)
  const shown = riskyOnly
    ? rows.filter(
        (row) => row.kind === 'checkpoint' && route.checkpoints[row.index].risk.level !== 'low',
      )
    : rows

  return (
    <details className="checkpoint-table">
      <summary>
        Checkpoint details for Route {route.id} ({route.checkpoints.length} checkpoints)
      </summary>
      <label className="checkpoint-table__filter">
        <input
          type="checkbox"
          checked={riskyOnly}
          onChange={(event) => setRiskyOnly(event.target.checked)}
        />
        Only show checkpoints above Low
      </label>
      {shown.length === 0 ? (
        <p className="checkpoint-table__empty">Every checkpoint on this route is Low risk.</p>
      ) : (
        <div className="checkpoint-table__scroll">
          <table>
            <caption className="visually-hidden">
              Weather risk at each checkpoint on Route {route.id}, and the driver's required stops
            </caption>
            <thead>
              <tr>
                <th scope="col">Mile</th>
                <th scope="col">Time</th>
                <th scope="col">Risk</th>
                <th scope="col">Weather</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => {
                if (row.kind === 'stop') {
                  const stop = route.rest_stops[row.index]
                  const length = formatDuration(
                    (Date.parse(stop.ends_utc) - Date.parse(stop.starts_utc)) / 1000,
                  )
                  return (
                    <tr key={`stop-${row.index}`} className="checkpoint-table__stop">
                      <td>{Math.round(stop.mile)}</td>
                      <td>{formatClock(stop.starts_utc, timeZone)}</td>
                      <td colSpan={2}>
                        {length} {stop.kind === 'rest' ? 'rest' : 'break'} (until{' '}
                        {formatClock(stop.ends_utc, timeZone)})
                      </td>
                    </tr>
                  )
                }
                const checkpoint = route.checkpoints[row.index]
                const { level, reasons } = checkpoint.risk
                const style = riskStyle(level)
                return (
                  <tr key={`checkpoint-${row.index}`}>
                    <td>{Math.round(checkpoint.mile)}</td>
                    <td>{formatClock(checkpoint.eta_utc, timeZone)}</td>
                    <td>
                      <span className="checkpoint-table__level">
                        <span
                          className="checkpoint-table__swatch"
                          style={{ background: style.color }}
                          aria-hidden="true"
                        />
                        {style.label}
                      </span>
                      {reasons.length > 0 && (
                        <span className="checkpoint-table__reasons">{reasons.join(', ')}</span>
                      )}
                    </td>
                    <td>{formatWeather(checkpoint.weather)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </details>
  )
}
