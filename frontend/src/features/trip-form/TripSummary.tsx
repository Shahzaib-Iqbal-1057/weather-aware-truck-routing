import type { TripPlanResponse } from '../../api/types'

function formatDeparture(utc: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(utc))
}

export function TripSummary({ plan }: { plan: TripPlanResponse }) {
  const { trip, warnings } = plan
  return (
    <section className="trip-summary" aria-label="Trip summary">
      <h2>Trip</h2>
      <dl>
        <dt>From</dt>
        <dd>{trip.origin.label}</dd>
        <dt>To</dt>
        <dd>{trip.destination.label}</dd>
        <dt>Departs</dt>
        <dd>{formatDeparture(trip.departure_utc, trip.departure_timezone)}</dd>
        <dt>Cargo</dt>
        <dd>{trip.cargo_weight_lb.toLocaleString('en-US')} lb</dd>
      </dl>
      {warnings.map((warning) => (
        <p key={warning} className="field__warning">
          {warning}
        </p>
      ))}
    </section>
  )
}
