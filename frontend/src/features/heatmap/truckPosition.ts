import type { RouteResult } from '../../api/types'

/**
 * Where the truck would be at `atMs` (epoch ms): between checkpoints by their ETAs, and parked at a
 * driver stop for its whole duration. Before departure it is at the start, after arrival at the end.
 */
export function truckPositionAt(route: RouteResult, atMs: number): [number, number] | null {
  const timeline: { at: number; position: [number, number] }[] = [
    ...route.checkpoints.map((c) => ({ at: Date.parse(c.eta_utc), position: c.position })),
    ...route.rest_stops.flatMap((stop) => [
      { at: Date.parse(stop.starts_utc), position: stop.position },
      { at: Date.parse(stop.ends_utc), position: stop.position },
    ]),
  ].sort((a, b) => a.at - b.at)

  if (timeline.length === 0) return null
  if (atMs <= timeline[0].at) return timeline[0].position
  for (let i = 1; i < timeline.length; i++) {
    const before = timeline[i - 1]
    const after = timeline[i]
    if (atMs <= after.at) {
      const t = after.at === before.at ? 1 : (atMs - before.at) / (after.at - before.at)
      return [
        before.position[0] + t * (after.position[0] - before.position[0]),
        before.position[1] + t * (after.position[1] - before.position[1]),
      ]
    }
  }
  return timeline[timeline.length - 1].position
}
