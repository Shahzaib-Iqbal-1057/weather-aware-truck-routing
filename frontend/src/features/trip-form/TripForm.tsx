import { useState, type FormEvent } from 'react'
import type { Place, TripPlanRequest } from '../../api/types'
import {
  browserTimeZone,
  defaultDeparture,
  timeZoneAbbreviation,
  wallClockInZone,
  zonedWallClockToUtc,
} from '../../lib/zonedTime'
import { useNow } from '../../lib/useNow'
import { PlaceAutocomplete } from './PlaceAutocomplete'
import './TripForm.css'
import {
  CARGO_MAX_LB,
  CARGO_MIN_LB,
  EMPTY_TRUCK_LB,
  LEGAL_GROSS_LB,
  MAX_DEPARTURE_AHEAD_DAYS,
} from './rules'
import {
  departureWarning,
  validateTripForm,
  type TripFormErrors,
  type TripFormField,
  type TripFormValues,
} from './validation'

interface TripFormProps {
  onSubmit: (request: TripPlanRequest) => void
  isSubmitting: boolean
  serverErrors: TripFormErrors
  generalError: string | null
  id?: string
  /** Folded away (but kept, with its values) once a trip is planned. */
  hidden?: boolean
}

const DAY_MS = 24 * 3_600_000
const QUARTER_HOUR_MS = 15 * 60_000

// Form values that are fields the server can report errors on.
const FIELD_KEYS: Record<TripFormField, true> = {
  origin: true,
  destination: true,
  departureLocal: true,
  cargoWeightLb: true,
}

/** The values with the departure the form shows: the user's, or "now" if they haven't set one. */
function withDefaultDeparture(values: TripFormValues, edited: boolean, now: Date): TripFormValues {
  return edited
    ? values
    : { ...values, departureLocal: defaultDeparture(now, values.departureTimeZone) }
}

export function TripForm({
  onSubmit,
  isSubmitting,
  serverErrors,
  generalError,
  id,
  hidden = false,
}: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(() => {
    const timeZone = browserTimeZone()
    return {
      origin: null,
      destination: null,
      departureLocal: defaultDeparture(new Date(), timeZone),
      departureTimeZone: timeZone,
      cargoWeightLb: '',
    }
  })
  const [departureEdited, setDepartureEdited] = useState(false)
  const [clientErrors, setClientErrors] = useState<TripFormErrors>({})
  const [submitted, setSubmitted] = useState(false)
  // Fields edited since the last submit: the server's verdict on them is out of date.
  const [editedSinceSubmit, setEditedSinceSubmit] = useState<ReadonlySet<TripFormField>>(new Set())

  const currentServerErrors = Object.fromEntries(
    Object.entries(serverErrors).filter(
      ([field]) => !editedSinceSubmit.has(field as TripFormField),
    ),
  )
  const errors = { ...currentServerErrors, ...clientErrors }
  const now = useNow()
  // Until the user picks a departure, the default stays "now" (to the next quarter hour), so a
  // form left open for a while, or reopened with "Change trip", never submits a past time.
  const shown = withDefaultDeparture(values, departureEdited, now)

  function update(patch: Partial<TripFormValues>) {
    const next = { ...values, ...patch }
    setValues(next)
    const fields = Object.keys(patch).filter((key): key is TripFormField => key in FIELD_KEYS)
    setEditedSinceSubmit((previous) => new Set([...previous, ...fields]))
    // After the first submit attempt, keep errors in sync as the user fixes them.
    const edited = departureEdited || 'departureLocal' in patch
    if (submitted) {
      const at = new Date()
      setClientErrors(validateTripForm(withDefaultDeparture(next, edited, at), at))
    }
  }

  function handleOriginChange(origin: Place | null) {
    // The departure is a local time at the origin; an unedited default follows the new zone.
    update({ origin, departureTimeZone: origin?.timezone ?? browserTimeZone() })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    setEditedSinceSubmit(new Set())
    const submittedAt = new Date()
    const current = withDefaultDeparture(values, departureEdited, submittedAt)
    const found = validateTripForm(current, submittedAt)
    setClientErrors(found)
    if (Object.keys(found).length > 0 || !current.origin || !current.destination) return

    const { origin, destination } = current
    onSubmit({
      origin: { label: origin.label, lat: origin.lat, lon: origin.lon, kind: origin.kind },
      destination: {
        label: destination.label,
        lat: destination.lat,
        lon: destination.lon,
        kind: destination.kind,
      },
      departure_local: current.departureLocal,
      cargo_weight_lb: Number(current.cargoWeightLb),
    })
  }

  const fieldError = (field: TripFormField) => errors[field]
  const departureInstant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(shown.departureLocal)
    ? zonedWallClockToUtc(shown.departureLocal, shown.departureTimeZone)
    : now
  const zoneAbbr = timeZoneAbbreviation(departureInstant, shown.departureTimeZone)
  const warning = departureWarning(shown, now)
  // The picker steps in quarter hours counted from `min`, so `min` sits on a quarter hour too.
  const earliest = new Date(Math.floor(now.getTime() / QUARTER_HOUR_MS) * QUARTER_HOUR_MS)

  return (
    <form id={id} className="trip-form" onSubmit={handleSubmit} noValidate hidden={hidden}>
      <PlaceAutocomplete
        label="Origin"
        placeholder="City or address"
        value={values.origin}
        onChange={handleOriginChange}
        error={fieldError('origin')}
      />
      <PlaceAutocomplete
        label="Destination"
        placeholder="City or address"
        value={values.destination}
        onChange={(destination) => update({ destination })}
        error={fieldError('destination')}
      />

      <div className="field">
        <label htmlFor="departure">Departure ({zoneAbbr})</label>
        <input
          id="departure"
          type="datetime-local"
          step={900}
          min={wallClockInZone(earliest, values.departureTimeZone)}
          max={wallClockInZone(
            new Date(earliest.getTime() + MAX_DEPARTURE_AHEAD_DAYS * DAY_MS),
            values.departureTimeZone,
          )}
          value={shown.departureLocal}
          aria-invalid={Boolean(fieldError('departureLocal'))}
          onChange={(event) => {
            setDepartureEdited(true)
            update({ departureLocal: event.target.value })
          }}
        />
        <p className="field__hint">
          {values.origin
            ? `Local time at the origin (${values.departureTimeZone.replaceAll('_', ' ')}).`
            : 'Local time at the origin. Choose an origin to set its time zone.'}
        </p>
        {warning && !fieldError('departureLocal') && <p className="field__warning">{warning}</p>}
        {fieldError('departureLocal') && (
          <p className="field__error">{fieldError('departureLocal')}</p>
        )}
      </div>

      <div className="field">
        <label htmlFor="cargo-weight">Cargo weight (lb)</label>
        <input
          id="cargo-weight"
          type="number"
          inputMode="numeric"
          min={CARGO_MIN_LB}
          max={CARGO_MAX_LB}
          step={1}
          placeholder="e.g. 30000"
          value={values.cargoWeightLb}
          aria-invalid={Boolean(fieldError('cargoWeightLb'))}
          onChange={(event) => update({ cargoWeightLb: event.target.value })}
        />
        <p className="field__hint">
          Freight only, up to {CARGO_MAX_LB.toLocaleString('en-US')} lb. The truck itself is assumed
          to weigh {EMPTY_TRUCK_LB.toLocaleString('en-US')} lb (
          {LEGAL_GROSS_LB.toLocaleString('en-US')} lb legal maximum in total).
        </p>
        {fieldError('cargoWeightLb') && (
          <p className="field__error">{fieldError('cargoWeightLb')}</p>
        )}
      </div>

      {generalError && (
        <p className="trip-form__error" role="alert">
          {generalError}
        </p>
      )}

      <button type="submit" className="trip-form__submit" disabled={isSubmitting}>
        {isSubmitting ? 'Planning…' : 'Plan trip'}
      </button>
    </form>
  )
}
