import {
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useRef, useState } from 'react'
import type { Place, RouteId, RouteResult } from '../../api/types'
import { endpointFeatures, routeFeatures, routesBounds } from './geojson'
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
}

const ROUTES_SOURCE = 'routes'
const ENDPOINTS_SOURCE = 'endpoints'
const ROUTE_LINE_LAYER = 'route-line'
// Draw the selected route above the others.
const SELECTED_FIRST: ExpressionSpecification = ['case', ['get', 'selected'], 1, 0]
// Labels: a lower sort key wins placement, so the selected route's letters win collisions.
const SELECTED_LABEL_FIRST: ExpressionSpecification = ['case', ['get', 'selected'], 0, 1]

export function RouteMap({
  routes,
  origin,
  destination,
  selectedId,
  onSelect,
  isLoading,
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
    id: 'route-label',
    type: 'symbol',
    source: ROUTES_SOURCE,
    layout: {
      // Repeat the letter along the line so each route stays identifiable at any zoom.
      'symbol-placement': 'line',
      'symbol-spacing': 300,
      'symbol-sort-key': SELECTED_LABEL_FIRST,
      'text-field': ['get', 'id'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 14,
      'text-keep-upright': true,
    },
    paint: { 'text-color': INK_COLOR, 'text-halo-color': ROUTE_CASING_COLOR, 'text-halo-width': 2 },
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
}
