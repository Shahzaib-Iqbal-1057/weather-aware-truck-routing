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
import type { HeatmapResponse, Place, RouteId, RouteResult } from '../../api/types'
import { CELL_RADIUS_MAX_ZOOM, cellRadiusStops, heatmapFeatures } from '../heatmap/heatmapFeatures'
import {
  checkpointFeatures,
  endpointFeatures,
  restStopFeatures,
  riskStretchFeatures,
  routeFeatures,
  routesBounds,
} from './geojson'
import { RISK_LEVELS } from '../../lib/risk'
import { createRouteBubble } from './routeBubble'
import { RiskLegend } from './RiskLegend'
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
  /** Times are shown on the departure city's clock. */
  timeZone: string
  /** Weather map (Stage 8) and the hour it shows; undefined when off. */
  heatmap: HeatmapResponse | undefined
  heatmapHour: number
  /** [lon, lat] of the truck at the weather map's hour, on the selected route. */
  truckPosition: [number, number] | null
}

const HEATMAP_SOURCE = 'heatmap'
const HEATMAP_LAYER = 'heatmap-cells'
// Low and unknown are transparent so only weather that matters stands out. Each cell is a soft
// disc that fades out towards its neighbours, so the cells blend instead of showing a grid.
const HEATMAP_OPACITY = 0.5
const HEATMAP_BLUR = 0.85
const HEATMAP_TILE_ZOOM = 6
const ROUTES_SOURCE = 'routes'
const ENDPOINTS_SOURCE = 'endpoints'
const CHECKPOINTS_SOURCE = 'checkpoints'
const REST_STOPS_SOURCE = 'rest-stops'
const RISK_STRETCHES_SOURCE = 'risk-stretches'
const ROUTE_LINE_LAYER = 'route-line'
const RISK_STRETCH_LAYER = 'route-risk'
// Clicking a route's line, or the risk drawn on it, selects that route.
const ROUTE_CLICK_LAYERS = [ROUTE_LINE_LAYER, RISK_STRETCH_LAYER]
const CHECKPOINT_LAYER = 'checkpoint-dots'
const CHECKPOINT_SPARSE_LAYER = 'checkpoint-dots-sparse'
// Below this zoom 10-mile dots overlap, so only some are drawn (see checkpointFeatures).
const ALL_CHECKPOINTS_FROM_ZOOM = 6.5
const REST_STOP_LAYER = 'rest-stop-markers'
const RISK_COLOR_BY_LEVEL = [
  'match',
  ['get', 'level'],
  ...RISK_LEVELS.flatMap((level) => [level.key, level.color]),
  RISK_LEVELS[RISK_LEVELS.length - 1].color,
] as unknown as ExpressionSpecification
// Hovering (or tapping) near one of these shows its `label` property in a small popup.
const LABELLED_LAYERS = [REST_STOP_LAYER, CHECKPOINT_LAYER, CHECKPOINT_SPARSE_LAYER]
// Pixels around the pointer that count as "on" a point, so the small dots are easy to hit.
const HOVER_RADIUS_PX = 8
// Draw the selected route above the others.
const SELECTED_FIRST: ExpressionSpecification = ['case', ['get', 'selected'], 1, 0]
// Worse weather is drawn on top where dots or stretches overlap.
const WORSE_FIRST = [
  'match',
  ['get', 'level'],
  ...RISK_LEVELS.flatMap((level, i) => [level.key, level.key === 'unknown' ? -1 : i]),
  0,
] as unknown as ExpressionSpecification
// The route line is wider than the risk drawn on it, so the route's own colour (blue when
// selected, gray otherwise) still frames a risky stretch.
const LINE_WIDTH: ExpressionSpecification = ['case', ['get', 'selected'], 7, 5]
const RISK_WIDTH: ExpressionSpecification = ['case', ['get', 'selected'], 4.5, 3]
const CASING_WIDTH: ExpressionSpecification = ['case', ['get', 'selected'], 10, 7.5]

/** Fill colour for the given hour: each cell carries every hour's level as `h0` … `h47`. */
function heatmapColorAt(hour: number): ExpressionSpecification {
  return [
    'match',
    ['get', `h${hour}`],
    ...RISK_LEVELS.slice(1, 5).flatMap((level, i) => [i + 1, level.color]),
    'rgba(0, 0, 0, 0)',
  ] as unknown as ExpressionSpecification
}

export function RouteMap({
  routes,
  origin,
  destination,
  selectedId,
  onSelect,
  timeZone,
  heatmap,
  heatmapHour,
  truckPosition,
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
      // Open-Meteo's data licence (CC BY 4.0) requires attribution.
      attributionControl: {
        customAttribution: 'Weather data by <a href="https://open-meteo.com/">Open-Meteo.com</a>',
      },
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map

    map.on('load', () => {
      addRouteLayers(map)
      map.on('click', ROUTE_CLICK_LAYERS, (event) => {
        const id = event.features?.[0]?.properties?.id as RouteId | undefined
        if (id) onSelectRef.current(id)
      })
      map.on('mouseenter', ROUTE_CLICK_LAYERS, () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', ROUTE_CLICK_LAYERS, () => (map.getCanvas().style.cursor = ''))
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
    map
      .getSource<GeoJSONSource>(RISK_STRETCHES_SOURCE)
      ?.setData(riskStretchFeatures(routes, selectedId))
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

  // Weather map: new data replaces the cells; a new hour only restyles them (no data re-sent).
  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    map.getSource<GeoJSONSource>(HEATMAP_SOURCE)?.setData(heatmapFeatures(heatmap))
    map.setPaintProperty(HEATMAP_LAYER, 'circle-radius', heatmapRadius(heatmap))
  }, [isReady, heatmap])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady) return
    map.setPaintProperty(HEATMAP_LAYER, 'circle-color', heatmapColorAt(heatmapHour))
  }, [isReady, heatmapHour])

  // The truck at the weather map's hour.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !isReady || !truckPosition) return
    const element = document.createElement('div')
    element.className = 'truck-marker'
    element.title = 'Truck at this hour'
    element.textContent = '🚚'
    const marker = new Marker({ element }).setLngLat(truckPosition).addTo(map)
    return () => {
      marker.remove()
    }
  }, [isReady, truckPosition])

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
      mapRef.current.fitBounds(bounds, { padding: 60, duration: prefersReducedMotion() ? 0 : 600 })
    }
  }, [isReady, routes])

  return (
    <div className="route-map">
      <div ref={containerRef} className="route-map__canvas" />
      {routes.length > 0 && <RiskLegend />}
    </div>
  )
}

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/** Grows with the zoom so each disc keeps covering its cell on the ground. */
function heatmapRadius(heatmap: HeatmapResponse | undefined): ExpressionSpecification {
  const [atZoom0, atMaxZoom] = cellRadiusStops(heatmap)
  return ['interpolate', ['exponential', 2], ['zoom'], 0, atZoom0, CELL_RADIUS_MAX_ZOOM, atMaxZoom]
}

function addRouteLayers(map: MapLibreMap) {
  // The weather map goes underneath everything route-related.
  // A disc can be wider than a map tile when zoomed in, and MapLibre clips each tile's drawing at
  // its edge. Tiling the cells at a low zoom with the widest buffer keeps every disc whole: tiles
  // are then scaled up when zooming in, so the buffer grows with the discs.
  map.addSource(HEATMAP_SOURCE, {
    type: 'geojson',
    data: heatmapFeatures(undefined),
    maxzoom: HEATMAP_TILE_ZOOM,
    buffer: 512,
  })
  map.addLayer({
    id: HEATMAP_LAYER,
    type: 'circle',
    source: HEATMAP_SOURCE,
    paint: {
      'circle-color': heatmapColorAt(0),
      'circle-radius': heatmapRadius(undefined),
      'circle-blur': HEATMAP_BLUR,
      'circle-opacity': HEATMAP_OPACITY,
      'circle-pitch-alignment': 'map',
    },
  })
  map.addSource(ROUTES_SOURCE, { type: 'geojson', data: routeFeatures([], null) })
  map.addSource(RISK_STRETCHES_SOURCE, { type: 'geojson', data: riskStretchFeatures([], null) })
  map.addSource(ENDPOINTS_SOURCE, { type: 'geojson', data: endpointFeatures(null, null) })
  map.addSource(CHECKPOINTS_SOURCE, { type: 'geojson', data: checkpointFeatures(null, 'UTC') })
  map.addSource(REST_STOPS_SOURCE, { type: 'geojson', data: restStopFeatures(null, 'UTC') })

  map.addLayer({
    id: 'route-casing',
    type: 'line',
    source: ROUTES_SOURCE,
    layout: { 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': SELECTED_FIRST },
    paint: { 'line-color': ROUTE_CASING_COLOR, 'line-width': CASING_WIDTH },
  })
  map.addLayer({
    id: ROUTE_LINE_LAYER,
    type: 'line',
    source: ROUTES_SOURCE,
    layout: { 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': SELECTED_FIRST },
    paint: {
      'line-color': ['case', ['get', 'selected'], ROUTE_SELECTED_COLOR, ROUTE_ALTERNATIVE_COLOR],
      'line-width': LINE_WIDTH,
    },
  })
  map.addLayer({
    id: RISK_STRETCH_LAYER,
    type: 'line',
    source: RISK_STRETCHES_SOURCE,
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
      // Selected route above the others, then worse weather above milder.
      'line-sort-key': ['+', ['*', SELECTED_FIRST, 10], WORSE_FIRST],
    },
    paint: { 'line-color': RISK_COLOR_BY_LEVEL, 'line-width': RISK_WIDTH },
  })
  const checkpointPaint = {
    'circle-radius': 4.5,
    'circle-color': RISK_COLOR_BY_LEVEL,
    // White ring separates the dot from the route line and from neighbouring dots.
    'circle-stroke-color': ROUTE_CASING_COLOR,
    'circle-stroke-width': 1.5,
  }
  map.addLayer({
    id: CHECKPOINT_LAYER,
    type: 'circle',
    source: CHECKPOINTS_SOURCE,
    minzoom: ALL_CHECKPOINTS_FROM_ZOOM,
    layout: { 'circle-sort-key': WORSE_FIRST },
    paint: checkpointPaint,
  })
  map.addLayer({
    id: CHECKPOINT_SPARSE_LAYER,
    type: 'circle',
    source: CHECKPOINTS_SOURCE,
    maxzoom: ALL_CHECKPOINTS_FROM_ZOOM,
    filter: ['get', 'keepZoomedOut'],
    layout: { 'circle-sort-key': WORSE_FIRST },
    paint: checkpointPaint,
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
