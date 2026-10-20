import { RISK_LEVELS } from '../../lib/risk'

/** Names every risk colour on the map, so colour is never the only way to read a level. */
export function RiskLegend() {
  return (
    <section className="risk-legend" aria-label="Risk levels">
      <h2 className="risk-legend__title">Weather risk</h2>
      <ul>
        {RISK_LEVELS.map((level) => (
          <li key={level.key}>
            <span
              className="risk-legend__swatch"
              style={{ background: level.color }}
              aria-hidden="true"
            />
            {level.label}
          </li>
        ))}
      </ul>
    </section>
  )
}
