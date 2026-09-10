import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, StatCard, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import type { CpiAirfareTrend, CpiAirfareIndex } from '../types'

export default function Data() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=36')
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')

  if (trend.loading) return <LoadingState label="Loading observations..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <div>
        <PageHeader title="Data" subtitle="CPI airfare observations" />
        <Card>
          <EmptyState message="No observations yet. The backend fetches index data shortly after startup." />
        </Card>
      </div>
    )
  }

  const rows = data.map((p, i) => {
    const prev = i > 0 ? data[i - 1].airfare_index : null
    const momPct = prev && prev > 0 ? ((p.airfare_index - prev) / prev) * 100 : null
    return { ...p, mom_pct: momPct }
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Data"
        subtitle={
          <>
            CPI airfare observations · base 2024=100 · {rows.length} months
          </>
        }
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Months available" value={rows.length} sub="of published index history" />
        <StatCard
          label="Latest airfare CPI"
          value={current.data?.airfare_index?.toFixed(2) ?? '\u2014'}
          sub={current.data?.period ?? ''}
          accent
        />
        <StatCard
          label="Latest YoY inflation"
          value={current.data?.inflation_yoy != null ? <TrendPill value={current.data.inflation_yoy} /> : '\u2014'}
          sub="year over year"
        />
      </div>
      <Card>
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-slate-50">
                <th className="py-2.5 px-3 font-medium">Period</th>
                <th className="py-2.5 px-3 text-right font-medium">Airfare CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Transport CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">MoM %</th>
                <th className="py-2.5 px-3 text-right font-medium">YoY %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.period} className="border-b border-lineSoft hover:bg-slate-50 transition-colors">
                  <td className="py-2 px-3 font-medium text-ink">{p.period}</td>
                  <td className="py-2 px-3 text-right tabular-nums">{p.airfare_index.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right tabular-nums text-muted">
                    {p.transport_index != null ? p.transport_index.toFixed(2) : '\u2014'}
                  </td>
                  <td className="py-2 px-3 text-right"><TrendPill value={p.mom_pct} /></td>
                  <td className="py-2 px-3 text-right"><TrendPill value={p.inflation_yoy} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}