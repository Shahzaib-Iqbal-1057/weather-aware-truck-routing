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

interface TripSummaryProps {
  plan: TripPlanResponse
  /** Whether the trip form is shown (it is folded away once a trip is planned). */
  editing: boolean
  onToggleEditing: () => void
  formId: string
}

/** The planned trip in two lines, with a button that unfolds the form to change it. */
export function TripSummary({ plan, editing, onToggleEditing, formId }: TripSummaryProps) {
  const { trip, warnings } = plan
  return (
    <section className="trip-summary" aria-label="Planned trip">
      <div className="trip-summary__row">
        <div>
          <p className="trip-summary__places">
            {trip.origin.label} <span aria-label="to">→</span> {trip.destination.label}
          </p>
          <p className="trip-summary__details">
            Departs {formatDeparture(trip.departure_utc, trip.departure_timezone)} ·{' '}
            {trip.cargo_weight_lb.toLocaleString('en-US')} lb cargo
          </p>
        </div>
        <button
          type="button"
          className="trip-summary__edit"
          aria-expanded={editing}
          aria-controls={formId}
          onClick={onToggleEditing}
        >
          {editing ? 'Cancel' : 'Change trip'}
        </button>
      </div>
      {warnings.map((warning) => (
        <p key={warning} className="field__warning">
          {warning}
        </p>
      ))}
    </section>
  )
}
