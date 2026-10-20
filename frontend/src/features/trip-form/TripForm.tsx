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

// Form values that are fields the server can report errors on.
const FIELD_KEYS: Record<TripFormField, true> = {
  origin: true,
  destination: true,
  departureLocal: true,
  cargoWeightLb: true,
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

  function update(patch: Partial<TripFormValues>) {
    const next = { ...values, ...patch }
    setValues(next)
    const edited = Object.keys(patch).filter((key): key is TripFormField => key in FIELD_KEYS)
    setEditedSinceSubmit((previous) => new Set([...previous, ...edited]))
    // After the first submit attempt, keep errors in sync as the user fixes them.
    if (submitted) setClientErrors(validateTripForm(next, new Date()))
  }

  function handleOriginChange(origin: Place | null) {
    const timeZone = origin?.timezone ?? browserTimeZone()
    // The departure is a local time at the origin. Until the user picks one,
    // keep the default ("now") correct for the new origin's zone.
    const departureLocal = departureEdited
      ? values.departureLocal
      : defaultDeparture(new Date(), timeZone)
    update({ origin, departureTimeZone: timeZone, departureLocal })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    setEditedSinceSubmit(new Set())
    const found = validateTripForm(values, new Date())
    setClientErrors(found)
    if (Object.keys(found).length > 0 || !values.origin || !values.destination) return

    const { origin, destination } = values
    onSubmit({
      origin: { label: origin.label, lat: origin.lat, lon: origin.lon, kind: origin.kind },
      destination: {
        label: destination.label,
        lat: destination.lat,
        lon: destination.lon,
        kind: destination.kind,
      },
      departure_local: values.departureLocal,
      cargo_weight_lb: Number(values.cargoWeightLb),
    })
  }

  const fieldError = (field: TripFormField) => errors[field]
  const departureInstant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(values.departureLocal)
    ? zonedWallClockToUtc(values.departureLocal, values.departureTimeZone)
    : now
  const zoneAbbr = timeZoneAbbreviation(departureInstant, values.departureTimeZone)
  const warning = departureWarning(values, now)

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
          min={wallClockInZone(now, values.departureTimeZone)}
          max={wallClockInZone(
            new Date(now.getTime() + MAX_DEPARTURE_AHEAD_DAYS * DAY_MS),
            values.departureTimeZone,
          )}
          value={values.departureLocal}
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
