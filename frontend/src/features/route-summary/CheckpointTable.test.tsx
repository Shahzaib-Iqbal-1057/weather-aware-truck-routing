import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Checkpoint } from '../../api/types'
import { makeRoute } from '../../test/fixtures'
import { CheckpointTable } from './CheckpointTable'

function checkpoint(mile: number, level: Checkpoint['risk']['level'], reasons: string[] = []) {
  return {
    position: [-100, 35] as [number, number],
    mile,
    eta_utc: '2026-10-20T14:00:00Z',
    weather: null,
    risk: { level, reasons },
  }
}

const ROUTE = makeRoute({
  id: 'B',
  checkpoints: [
    checkpoint(0, 'low'),
    checkpoint(10, 'high', ['Gusts 57.3 mph']),
    checkpoint(20, 'unknown'),
  ],
  rest_stops: [
    {
      kind: 'break',
      position: [-100, 35],
      mile: 15,
      starts_utc: '2026-10-20T22:00:00Z',
      ends_utc: '2026-10-20T22:30:00Z',
    },
  ],
})

function rows() {
  return within(screen.getAllByRole('rowgroup')[1]).getAllByRole('row') as HTMLTableRowElement[]
}

describe('CheckpointTable', () => {
  it('lists checkpoints and driver stops in mile order with level and reasons', () => {
    render(<CheckpointTable route={ROUTE} timeZone="America/Chicago" />)

    expect(rows().map((row) => row.cells[0].textContent)).toEqual(['0', '10', '15', '20'])
    expect(rows()[1]).toHaveTextContent('HighGusts 57.3 mph')
    expect(rows()[2]).toHaveTextContent('30 min break (until Tue 5:30 PM CDT)')
  })

  it('can show only the checkpoints at Moderate or worse', () => {
    render(<CheckpointTable route={ROUTE} timeZone="UTC" />)

    fireEvent.click(screen.getByLabelText('Only show Moderate or worse'))

    expect(rows().map((row) => row.cells[0].textContent)).toEqual(['10'])
  })
})
