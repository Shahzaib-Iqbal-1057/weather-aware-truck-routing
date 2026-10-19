import { useHealth } from '../api/health'

export function BackendStatus() {
  const { isPending, isError } = useHealth()

  if (isPending) return <span className="status">Connecting to API…</span>
  if (isError) return <span className="status status--error">API unreachable</span>
  return <span className="status status--ok">API connected</span>
}
