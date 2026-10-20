import type { RouteId, RouteResult } from '../../api/types'
import { formatDuration } from '../../lib/format'

export function routeBubbleText(route: RouteResult): string {
  return `${route.id} · ${formatDuration(route.trip_time_s)}`
}

/** The map label for a route: a button that selects the route when clicked. */
export function createRouteBubble(
  route: RouteResult,
  selected: boolean,
  onSelect: (id: RouteId) => void,
): HTMLButtonElement {
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'route-bubble'
  button.textContent = routeBubbleText(route)
  button.setAttribute(
    'aria-label',
    `Route ${route.id}, ${formatDuration(route.trip_time_s)} door to door`,
  )
  button.setAttribute('aria-pressed', String(selected))
  // Keep the selected route's bubble above the others where they overlap.
  button.style.zIndex = selected ? '2' : '1'
  button.addEventListener('click', (event) => {
    event.stopPropagation()
    onSelect(route.id)
  })
  return button
}
