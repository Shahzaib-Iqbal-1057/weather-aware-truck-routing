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
import { MAX_DEPARTURE_AHEAD_DAYS, WEIGHT_MAX_LB, WEIGHT_MIN_LB } from './rules'
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
}

const DAY_MS = 24 * 3_600_000

export function TripForm({ onSubmit, isSubmitting, serverErrors, generalError }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(() => {
    const timeZone = browserTimeZone()
    return {
      origin: null,
      destination: null,
      departureLocal: defaultDeparture(new Date(), timeZone),
      departureTimeZone: timeZone,
      weightLb: '',
    }
  })
  const [departureEdited, setDepartureEdited] = useState(false)
  const [clientErrors, setClientErrors] = useState<TripFormErrors>({})
  const [submitted, setSubmitted] = useState(false)

  const errors = { ...serverErrors, ...clientErrors }
  const now = useNow()

  function update(patch: Partial<TripFormValues>) {
    const next = { ...values, ...patch }
    setValues(next)
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
      weight_lb: Number(values.weightLb),
    })
  }

  const fieldError = (field: TripFormField) => errors[field]
  const departureInstant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(values.departureLocal)
    ? zonedWallClockToUtc(values.departureLocal, values.departureTimeZone)
    : now
  const zoneAbbr = timeZoneAbbreviation(departureInstant, values.departureTimeZone)
  const warning = departureWarning(values, now)

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate>
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
        <label htmlFor="weight">Total weight (lb)</label>
        <input
          id="weight"
          type="number"
          inputMode="numeric"
          min={WEIGHT_MIN_LB}
          max={WEIGHT_MAX_LB}
          step={1}
          placeholder="e.g. 65000"
          value={values.weightLb}
          aria-invalid={Boolean(fieldError('weightLb'))}
          onChange={(event) => update({ weightLb: event.target.value })}
        />
        <p className="field__hint">
          Truck plus cargo, up to {WEIGHT_MAX_LB.toLocaleString('en-US')} lb.
        </p>
        {fieldError('weightLb') && <p className="field__error">{fieldError('weightLb')}</p>}
      </div>

      {generalError && <p className="trip-form__error">{generalError}</p>}

      <button type="submit" className="trip-form__submit" disabled={isSubmitting}>
        {isSubmitting ? 'Planning…' : 'Plan trip'}
      </button>
    </form>
  )
}
