import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type MapMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useRef, useState } from 'react'
import type { Place, RouteId, RouteResult } from '../../api/types'
import {
  checkpointFeatures,
  endpointFeatures,
  restStopFeatures,
  routeFeatures,
  routesBounds,
} from './geojson'
import { createRouteBubble } from './routeBubble'
import {
  BASE_MAP_STYLE,
  CONTINENTAL_US_CENTER,
  CONTINENTAL_US_ZOOM,
  INK_COLOR,
  ROUTE_ALTERNATIVE_COLOR,
  ROUTE_CASING_COLOR,
  ROUTE_SELECTED_COLOR,
} from './mapStyle'
import './RouteMap.css'

// MapLibre looks for its worker next to its own file, which no longer holds once Vite bundles it.
// Importing the worker with `?url` makes Vite serve/emit it and gives us its real URL.
setWorkerUrl(workerUrl)

interface RouteMapProps {
  routes: RouteResult[]
  origin: Place | null
  destination: Place | null
  selectedId: RouteId | null
  onSelect: (id: RouteId) => void
  isLoading: boolean
  /** Times are shown on the departure city's clock. */
  timeZone: string
}

const ROUTES_SOURCE = 'routes'
const ENDPOINTS_SOURCE = 'endpoints'
const CHECKPOINTS_SOURCE = 'checkpoints'
const REST_STOPS_SOURCE = 'rest-stops'
const ROUTE_LINE_LAYER = 'route-line'
const CHECKPOINT_LAYER = 'checkpoint-dots'
const REST_STOP_LAYER = 'rest-stop-markers'
// Hovering (or tapping) near one of these shows its `label` property in a small popup.
const LABELLED_LAYERS = [REST_STOP_LAYER, CHECKPOINT_LAYER]
// Pixels around the pointer that count as "on" a point, so the small dots are easy to hit.
const HOVER_RADIUS_PX = 8
// Draw the selected route above the others.
const SELECTED_FIRST: ExpressionSpecification = ['case', ['get', 'selected'], 1, 0]

export function RouteMap({
  routes,
  origin,
  destination,
  selectedId,
  onSelect,
  isLoading,
  timeZone,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectRef = useRef(onSelect)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // Create the map once; sources and layers are added when the style has loaded.
  useEffect(() => {
    if (!containerRef.current) return
    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASE_MAP_STYLE,
      center: CONTINENTAL_US_CENTER,
      zoom: CONTINENTAL_US_ZOOM,
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map

    map.on('load', () => {
      addRouteLayers(map)
      map.on('click', ROUTE_LINE_LAYER, (event) => {
        const id = event.features?.[0]?.properties?.id as RouteId | undefined
        if (id) onSelectRef.current(id)
      })
      map.on('mouseenter', ROUTE_LINE_LAYER, () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', ROUTE_LINE_LAYER, () => (map.getCanvas().style.cursor = ''))
      showLabelsOnHover(map)
      setIsReady(true)
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    map.getSource<GeoJSONSource>(ROUTES_SOURCE)?.setData(routeFeatures(routes, selectedId))
  }, [isReady, routes, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    const selected = routes.find((route) => route.id === selectedId) ?? null
    map
      .getSource<GeoJSONSource>(CHECKPOINTS_SOURCE)
      ?.setData(checkpointFeatures(selected, timeZone))
    map.getSource<GeoJSONSource>(REST_STOPS_SOURCE)?.setData(restStopFeatures(selected, timeZone))
  }, [isReady, routes, selectedId, timeZone])

  // One clickable bubble per route ("A · 12 h 30 min"), on road no other route uses.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    const markers = routes.map((route) =>
      new Marker({
        element: createRouteBubble(route, route.id === selectedId, (id) => onSelectRef.current(id)),
      })
        .setLngLat(route.label_position)
        .addTo(map),
    )
    return () => markers.forEach((marker) => marker.remove())
  }, [isReady, routes, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    map.getSource<GeoJSONSource>(ENDPOINTS_SOURCE)?.setData(endpointFeatures(origin, destination))
  }, [isReady, origin, destination])

  // Frame the trip whenever a new set of routes arrives (not when the selection changes).
  useEffect(() => {
    const bounds = routesBounds(routes)
    if (mapRef.current && isReady && bounds) {
      mapRef.current.fitBounds(bounds, { padding: 60, duration: 600 })
    }
  }, [isReady, routes])

  return (
    <div className="route-map">
      <div ref={containerRef} className="route-map__canvas" />
      {isLoading && (
        <div className="route-map__overlay" role="status">
          Finding truck routes…
        </div>
      )}
    </div>
  )
}

function addRouteLayers(map: MapLibreMap) {
  map.addSource(ROUTES_SOURCE, { type: 'geojson', data: routeFeatures([], null) })
  map.addSource(ENDPOINTS_SOURCE, { type: 'geojson', data: endpointFeatures(null, null) })
  map.addSource(CHECKPOINTS_SOURCE, { type: 'geojson', data: checkpointFeatures(null, 'UTC') })
  map.addSource(REST_STOPS_SOURCE, { type: 'geojson', data: restStopFeatures(null, 'UTC') })

  map.addLayer({
    id: 'route-casing',
    type: 'line',
    source: ROUTES_SOURCE,
    layout: { 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': SELECTED_FIRST },
    paint: { 'line-color': ROUTE_CASING_COLOR, 'line-width': 7 },
  })
  map.addLayer({
    id: ROUTE_LINE_LAYER,
    type: 'line',
    source: ROUTES_SOURCE,
    layout: { 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': SELECTED_FIRST },
    paint: {
      'line-color': ['case', ['get', 'selected'], ROUTE_SELECTED_COLOR, ROUTE_ALTERNATIVE_COLOR],
      'line-width': ['case', ['get', 'selected'], 5, 3.5],
    },
  })
  map.addLayer({
    id: CHECKPOINT_LAYER,
    type: 'circle',
    source: CHECKPOINTS_SOURCE,
    paint: {
      'circle-radius': 3.5,
      'circle-color': ROUTE_CASING_COLOR,
      'circle-stroke-color': ROUTE_SELECTED_COLOR,
      'circle-stroke-width': 1.5,
    },
  })
  map.addLayer({
    id: 'endpoints',
    type: 'circle',
    source: ENDPOINTS_SOURCE,
    paint: {
      'circle-radius': 7,
      'circle-color': ['match', ['get', 'role'], 'origin', ROUTE_CASING_COLOR, INK_COLOR],
      'circle-stroke-color': INK_COLOR,
      'circle-stroke-width': 2.5,
    },
  })
  // Driver stops: a "P" (parking) disc in the route's colour, drawn above the start/end markers
  // so a rest near the destination stays visible. The 10-hour rest is larger than the 30-min break.
  map.addLayer({
    id: REST_STOP_LAYER,
    type: 'circle',
    source: REST_STOPS_SOURCE,
    paint: {
      'circle-radius': ['match', ['get', 'kind'], 'rest', 10, 8],
      'circle-color': ROUTE_SELECTED_COLOR,
      'circle-stroke-color': ROUTE_CASING_COLOR,
      'circle-stroke-width': 2,
    },
  })
  map.addLayer({
    id: 'rest-stop-letter',
    type: 'symbol',
    source: REST_STOPS_SOURCE,
    layout: {
      'text-field': 'P',
      'text-font': ['Noto Sans Bold'],
      'text-size': ['match', ['get', 'kind'], 'rest', 13, 11],
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: { 'text-color': ROUTE_CASING_COLOR },
  })
}

function showLabelsOnHover(map: MapLibreMap) {
  const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 10 })

  const update = (event: MapMouseEvent) => {
    const { x, y } = event.point
    const [feature] = map.queryRenderedFeatures(
      [
        [x - HOVER_RADIUS_PX, y - HOVER_RADIUS_PX],
        [x + HOVER_RADIUS_PX, y + HOVER_RADIUS_PX],
      ],
      { layers: LABELLED_LAYERS },
    )
    if (!feature || feature.geometry.type !== 'Point') {
      popup.remove()
      return
    }
    popup
      .setLngLat(feature.geometry.coordinates as [number, number])
      .setText(String(feature.properties?.label ?? ''))
      .addTo(map)
  }

  map.on('mousemove', update)
  map.on('click', update) // touch screens have no hover
  map.on('mouseout', () => popup.remove())
}
