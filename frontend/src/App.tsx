import { lazy, memo, Suspense, useCallback, useMemo, useState } from 'react'
import { ApiError } from './api/client'
import { useHeatmap, weatherAllowanceUsedUp } from './api/heatmap'
import { usePlanTrip } from './api/trips'
import type { RouteId, TripPlanRequest } from './api/types'
import { browserTimeZone } from './lib/zonedTime'
import { BackendStatus } from './components/BackendStatus'
import { MapErrorBoundary } from './components/MapErrorBoundary'
import { MapMessage } from './components/MapMessage'
import { HeatmapControl } from './features/heatmap/HeatmapControl'
import { hasWeatherAt } from './features/heatmap/heatmapFeatures'
import { truckPositionAt } from './features/heatmap/truckPosition'
import { CheckpointTable } from './features/route-summary/CheckpointTable'
import { RouteList } from './features/route-summary/RouteList'
import { toFormErrors } from './features/trip-form/serverErrors'
import { TripForm } from './features/trip-form/TripForm'
import { TripSummary } from './features/trip-form/TripSummary'
import './App.css'

// MapLibre is most of the bundle, so load it separately and let the form appear first.
const RouteMap = lazy(() =>
  import('./features/map/RouteMap').then((module) => ({ default: module.RouteMap })),
)

// Moving the weather map's slider re-renders App every hour step. The sidebar doesn't depend on
// the hour, so it skips those renders (its props are stable between them).
const Sidebar = {
  BackendStatus: memo(BackendStatus),
  TripSummary: memo(TripSummary),
  TripForm: memo(TripForm),
  RouteList: memo(RouteList),
  CheckpointTable: memo(CheckpointTable),
}

const GENERIC_ERROR = 'Could not plan the trip. Please try again.'
const TRIP_FORM_ID = 'trip-form'
// The departure hour and each of the 48 after it (the server's count, until it has answered).
const HEATMAP_HOURS = 49

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
  // Once a trip is planned the form folds into a one-line summary, so the routes come first.
  const [editing, setEditing] = useState(false)
  // Weather map: loaded only once the user turns it on (it costs a weather request per cell).
  const [heatmapOn, setHeatmapOn] = useState(false)
  const [heatmapHour, setHeatmapHour] = useState(0)
  const onHourChange = useCallback((hour: number) => setHeatmapHour(hour), [])
  const showHeatmap = useCallback(() => setHeatmapOn(true), [])
  const hideHeatmap = useCallback(() => setHeatmapOn(false), [])
  const toggleEditing = useCallback(() => setEditing((open) => !open), [])
  const { mutate } = planTrip
  const submitTrip = useCallback(
    (request: TripPlanRequest) => {
      setSelectedId(null)
      setHeatmapHour(0)
      mutate(request, { onSuccess: () => setEditing(false) })
    },
    [mutate],
  )

  const plan = planTrip.data
  const routes = plan?.routes ?? []
  const heatmap = useHeatmap(plan ? planTrip.variables : undefined, heatmapOn)
  // Show the recommended route until the user picks one (the fastest if nothing is recommended).
  const activeId = routes.some((route) => route.id === selectedId)
    ? selectedId
    : (plan?.recommendation.route_id ?? routes[0]?.id ?? null)
  const { fields: serverErrors, general } = useMemo(
    () => describeError(planTrip.error),
    [planTrip.error],
  )
  // All times are shown on the departure city's clock.
  const timeZone = plan?.trip.departure_timezone ?? browserTimeZone()

  const heatmapStart = heatmap.data?.start_utc ?? plan?.trip.departure_utc ?? ''
  const activeRoute = routes.find((route) => route.id === activeId)
  const truckPosition =
    heatmapOn && heatmap.data && activeRoute
      ? truckPositionAt(activeRoute, Date.parse(heatmapStart) + heatmapHour * 3_600_000)
      : null
  const heatmapStatus = heatmap.data
    ? 'ready'
    : weatherAllowanceUsedUp(heatmap.error)
      ? 'used-up'
      : heatmap.isError
        ? 'error'
        : heatmap.failureCount > 0
          ? 'busy'
          : 'loading'

  return (
    <div className={plan ? 'app app--planned' : 'app'}>
      <header className="app__header">
        <h1>Weather-Aware Truck Routing</h1>
        <Sidebar.BackendStatus />
      </header>
      <div className="app__body">
        <aside className="app__sidebar" aria-label="Trip planner">
          {plan && (
            <Sidebar.TripSummary
              plan={plan}
              editing={editing}
              onToggleEditing={toggleEditing}
              formId={TRIP_FORM_ID}
            />
          )}
          <Sidebar.TripForm
            id={TRIP_FORM_ID}
            hidden={Boolean(plan) && !editing}
            onSubmit={submitTrip}
            isSubmitting={planTrip.isPending}
            serverErrors={serverErrors}
            generalError={general}
          />
          {plan && (
            <>
              <Sidebar.RouteList
                routes={routes}
                notes={plan.notes}
                selectedId={activeId}
                onSelect={setSelectedId}
                timeZone={timeZone}
                destinationName={plan.trip.destination.label.split(',')[0]}
                recommendation={plan.recommendation}
              />
              {activeRoute && (
                <Sidebar.CheckpointTable
                  key={activeRoute.id}
                  route={activeRoute}
                  timeZone={timeZone}
                />
              )}
            </>
          )}
        </aside>
        <main className="app__map" aria-label="Map">
          <MapErrorBoundary>
            <Suspense fallback={null}>
              <RouteMap
                routes={routes}
                origin={plan?.trip.origin ?? null}
                destination={plan?.trip.destination ?? null}
                selectedId={activeId}
                onSelect={setSelectedId}
                timeZone={timeZone}
                heatmap={heatmapOn ? heatmap.data : undefined}
                heatmapHour={heatmapHour}
                truckPosition={truckPosition}
              />
            </Suspense>
          </MapErrorBoundary>
          {planTrip.isPending ? (
            <MapMessage busy>Finding truck routes and checking the weather…</MapMessage>
          ) : general ? (
            <MapMessage title="Could not plan this trip">{general}</MapMessage>
          ) : (
            !plan && (
              <MapMessage title="Plan a trip to see truck routes" hint>
                Pick a start, a destination, when you leave and the cargo weight. Up to three
                truck-legal routes appear here, coloured by the weather forecast for the hour the
                truck reaches each stretch.
              </MapMessage>
            )
          )}
          {plan && (
            <HeatmapControl
              enabled={heatmapOn}
              onEnable={showHeatmap}
              onDisable={hideHeatmap}
              hour={heatmapHour}
              onHourChange={onHourChange}
              hours={heatmap.data?.hours ?? HEATMAP_HOURS}
              startUtc={heatmapStart}
              timeZone={timeZone}
              status={heatmapStatus}
              hasWeather={hasWeatherAt(heatmap.data, heatmapHour)}
            />
          )}
        </main>
      </div>
    </div>
  )
}
