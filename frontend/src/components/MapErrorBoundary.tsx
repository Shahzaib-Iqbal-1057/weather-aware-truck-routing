import { Component, type ReactNode } from 'react'
import { MapMessage } from './MapMessage'

interface State {
  failed: boolean
}

/** If the map fails (e.g. no WebGL), the planner and route list keep working without it. */
export class MapErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <MapMessage title="The map could not be shown">
          Your routes and their weather are still listed beside it. Reloading the page may help.
        </MapMessage>
      )
    }
    return this.props.children
  }
}
