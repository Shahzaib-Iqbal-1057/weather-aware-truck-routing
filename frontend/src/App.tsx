import { lazy, Suspense, useState } from 'react'
import { ApiError } from './api/client'
import { usePlanTrip } from './api/trips'
import type { RouteId } from './api/types'
import { browserTimeZone } from './lib/zonedTime'
import { BackendStatus } from './components/BackendStatus'
import { RouteList } from './features/route-summary/RouteList'
import { toFormErrors } from './features/trip-form/serverErrors'
import { TripForm } from './features/trip-form/TripForm'
import { TripSummary } from './features/trip-form/TripSummary'
import './App.css'

// MapLibre is most of the bundle, so load it separately and let the form appear first.
const RouteMap = lazy(() =>
  import('./features/map/RouteMap').then((module) => ({ default: module.RouteMap })),
)

const GENERIC_ERROR = 'Could not plan the trip. Please try again.'

function describeError(error: Error | null) {
  if (!error) return { fields: {}, general: null }
  if (error instanceof ApiError && error.status === 400) return toFormErrors(error.body)
  const detail =
    error instanceof ApiError &&
    typeof error.body === 'object' &&
    error.body !== null &&
    'detail' in error.body &&
    typeof error.body.detail === 'string'
      ? error.body.detail
      : GENERIC_ERROR
  return { fields: {}, general: detail }
}

export default function App() {
  const planTrip = usePlanTrip()
  const [selectedId, setSelectedId] = useState<RouteId | null>(null)

  const plan = planTrip.data
  const routes = plan?.routes ?? []
  // Default to the first (fastest) route until the user picks one.
  const activeId = routes.some((route) => route.id === selectedId)
    ? selectedId
    : (routes[0]?.id ?? null)
  const { fields: serverErrors, general } = describeError(planTrip.error)
  // All times are shown on the departure city's clock.
  const timeZone = plan?.trip.departure_timezone ?? browserTimeZone()

  return (
    <div className="app">
      <header className="app__header">
        <h1>Weather-Aware Truck Routing</h1>
        <BackendStatus />
      </header>
      <div className="app__body">
        <aside className="app__sidebar">
          <TripForm
            onSubmit={(request) => {
              setSelectedId(null)
              planTrip.mutate(request)
            }}
            isSubmitting={planTrip.isPending}
            serverErrors={serverErrors}
            generalError={general}
          />
          {plan && (
            <>
              <RouteList
                routes={routes}
                notes={plan.notes}
                selectedId={activeId}
                onSelect={setSelectedId}
                timeZone={timeZone}
              />
              <TripSummary plan={plan} />
            </>
          )}
        </aside>
        <main className="app__map" aria-label="Map">
          <Suspense fallback={null}>
            <RouteMap
              routes={routes}
              origin={plan?.trip.origin ?? null}
              destination={plan?.trip.destination ?? null}
              selectedId={activeId}
              onSelect={setSelectedId}
              isLoading={planTrip.isPending}
              timeZone={timeZone}
            />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
