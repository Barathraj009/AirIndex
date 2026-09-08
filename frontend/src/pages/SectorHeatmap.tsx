import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IndexResult } from '../types'

function colorForChange(pct: number): string {
  // green (fare down) -> white -> red (fare up)
  const clamped = Math.max(-15, Math.min(15, pct))
  if (clamped >= 0) {
    const intensity = clamped / 15
    return `rgba(220, 38, 38, ${0.12 + intensity * 0.65})`
  }
  const intensity = -clamped / 15
  return `rgba(22, 163, 74, ${0.12 + intensity * 0.65})`
}

export default function SectorHeatmap() {
  const indexQuery = useApiQuery<IndexResult>('/index/current')

  if (indexQuery.loading) return <LoadingState label="Building heatmap…" />
  if (indexQuery.error) return <ErrorState message={indexQuery.error} />
  if (!indexQuery.data) return null

  const routeFares = indexQuery.data.route_fares
  const cities = new Set<string>()
  Object.keys(routeFares).forEach((r) => {
    const [o, d] = r.split('-')
    cities.add(o)
    cities.add(d)
  })
  const cityList = Array.from(cities).sort()

  if (cityList.length === 0) {
    return <EmptyState message="No route data available to build a heatmap yet." />
  }

  return (
    <div>
      <PageHeader title="Sector Heatmap" subtitle="Fare change (%) by origin–destination pair, base vs current period" />
      <Card>
        <div className="overflow-x-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-2"></th>
                {cityList.map((c) => (
                  <th key={c} className="p-2 font-semibold text-muted">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cityList.map((origin) => (
                <tr key={origin}>
                  <td className="p-2 font-semibold text-muted">{origin}</td>
                  {cityList.map((dest) => {
                    if (origin === dest) return <td key={dest} className="p-2 bg-slate-50" />
                    const forward = routeFares[`${origin}-${dest}`]
                    const backward = routeFares[`${dest}-${origin}`]
                    const detail = forward ?? backward
                    if (!detail) return <td key={dest} className="p-2 bg-slate-50 text-center text-slate-300">·</td>
                    const changePct = (detail.relative - 1) * 100
                    return (
                      <td
                        key={dest}
                        className="p-2 text-center font-medium rounded"
                        style={{ backgroundColor: colorForChange(changePct) }}
                        title={`${origin}-${dest}: ${changePct.toFixed(2)}%`}
                      >
                        {changePct.toFixed(1)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-2 mt-4 text-xs text-muted">
          <span>Cheaper</span>
          <div className="h-2 w-32 rounded" style={{ background: 'linear-gradient(to right, rgba(22,163,74,0.77), white, rgba(220,38,38,0.77))' }} />
          <span>More expensive</span>
        </div>
      </Card>
    </div>
  )
}
