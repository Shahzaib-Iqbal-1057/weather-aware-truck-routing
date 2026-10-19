import { ApiError } from './api/client'
import { usePlanTrip } from './api/trips'
import { BackendStatus } from './components/BackendStatus'
import { toFormErrors } from './features/trip-form/serverErrors'
import { TripForm } from './features/trip-form/TripForm'
import { TripSummary } from './features/trip-form/TripSummary'
import './App.css'

export default function App() {
  const planTrip = usePlanTrip()

  const { fields: serverErrors, general } =
    planTrip.error instanceof ApiError && planTrip.error.status === 400
      ? toFormErrors(planTrip.error.body)
      : {
          fields: {},
          general: planTrip.error ? 'Could not plan the trip. Please try again.' : null,
        }

  return (
    <div className="app">
      <header className="app__header">
        <h1>Weather-Aware Truck Routing</h1>
        <BackendStatus />
      </header>
      <div className="app__body">
        <aside className="app__sidebar">
          <TripForm
            onSubmit={(request) => planTrip.mutate(request)}
            isSubmitting={planTrip.isPending}
            serverErrors={serverErrors}
            generalError={general}
          />
          {planTrip.data && <TripSummary plan={planTrip.data} />}
        </aside>
        <main className="app__map" aria-label="Map">
          <p className="placeholder">Map (Stage 7)</p>
        </main>
      </div>
    </div>
  )
}
