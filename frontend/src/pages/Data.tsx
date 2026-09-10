import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, StatCard, LoadingState, ErrorState, EmptyState, SourceBadge } from '../components/ui'
import type { CpiAirfareTrend, CpiAirfareIndex } from '../types'

type DataTab = 'observations' | 'source'

const TABS: { key: DataTab; label: string }[] = [
  { key: 'observations', label: 'CPI Observations' },
  { key: 'source', label: 'Source & Freshness' },
]

export default function Data() {
  const [tab, setTab] = useState<DataTab>('observations')

  return (
    <div>
      <PageHeader title="Data" subtitle="CPI airfare observations from MoSPI" />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      {tab === 'observations' && <ObservationsTab />}
      {tab === 'source' && <SourceTab />}
    </div>
  )
}

function ObservationsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=36')
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')

  if (trend.loading) return <LoadingState label="Loading CPI observations..." />
  if (trend.error) return <ErrorState message={trend.error} />

  const data = trend.data?.series ?? []

  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="No CPI observations yet. The backend fetches MoSPI data shortly after startup." />
      </Card>
    )
  }

  // Compute month-over-month change for display
  const rows = data.map((p, i) => {
    const prev = i > 0 ? data[i - 1].airfare_index : null
    const momPct = prev && prev > 0 ? ((p.airfare_index - prev) / prev) * 100 : null
    return { ...p, mom_pct: momPct }
  })

  return (
    <div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Months available" value={rows.length} />
        <StatCard
          label="Latest airfare CPI"
          value={current.data?.airfare_index?.toFixed(2) ?? '\u2014'}
          sub={current.data?.period ?? ''}
        />
        <StatCard
          label="Latest YoY inflation"
          value={current.data?.inflation_yoy != null ? `${current.data.inflation_yoy.toFixed(2)}%` : '\u2014'}
        />
      </div>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2 pr-3">Period</th>
                <th className="py-2 pr-3 text-right">Airfare CPI</th>
                <th className="py-2 pr-3 text-right">Transport CPI</th>
                <th className="py-2 pr-3 text-right">General CPI</th>
                <th className="py-2 pr-3 text-right">MoM %</th>
                <th className="py-2 pr-3 text-right">YoY %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.period} className="border-b border-slate-100">
                  <td className="py-1.5 pr-3 font-medium">{p.period}</td>
                  <td className="py-1.5 pr-3 text-right">{p.airfare_index.toFixed(2)}</td>
                  <td className="py-1.5 pr-3 text-right text-muted">
                    {p.transport_index != null ? p.transport_index.toFixed(2) : '\u2014'}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-muted">
                    {p.general_index != null ? p.general_index.toFixed(2) : '\u2014'}
                  </td>
                  <td className="py-1.5 pr-3 text-right">
                    {p.mom_pct != null ? (
                      <span className={p.mom_pct >= 0 ? 'text-red-600' : 'text-emerald-600'}>
                        {p.mom_pct >= 0 ? '+' : ''}{p.mom_pct.toFixed(2)}%
                      </span>
                    ) : (
                      '\u2014'
                    )}
                  </td>
                  <td className="py-1.5 pr-3 text-right">
                    {p.inflation_yoy != null ? (
                      <span className={p.inflation_yoy >= 0 ? 'text-red-600' : 'text-emerald-600'}>
                        {p.inflation_yoy >= 0 ? '+' : ''}{p.inflation_yoy.toFixed(2)}%
                      </span>
                    ) : (
                      '\u2014'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted mt-3">
          Source: MoSPI Consolidated CPI (code 07.3.3.1, base 2024=100) via esankhyiki.mospi.gov.in.
        </p>
      </Card>
    </div>
  )
}

function SourceTab() {
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')

  if (current.loading) return <LoadingState label="Loading source info..." />
  if (current.error) return <ErrorState message={current.error} />

  const data = current.data

  return (
    <div>
      <Card className="mb-6">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Primary data source</span>
            <span className="font-medium">
              <SourceBadge sourceType="PUBLIC_DATASET" />
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Publisher</span>
            <span className="font-medium">Ministry of Statistics and Programme Implementation (MoSPI)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Portal</span>
            <a href="https://esankhyiki.mospi.gov.in" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              esankhyiki.mospi.gov.in
            </a>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">CPI code</span>
            <span className="font-medium">07.3.3.1 - Passenger transport by air, domestic</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Base year</span>
            <span className="font-medium">{data?.base_year ?? '2024=100'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Release cadence</span>
            <span className="font-medium">Monthly (published ~12th of following month)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Last fetched</span>
            <span className="font-medium">
              {data?.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'Not yet fetched'}
            </span>
          </div>
        </div>
      </Card>
      <Card>
        <p className="text-xs text-muted">
          The APIx platform ingests the official MoSPI Consolidated CPI series for the
          air transport sub-component. The backend refreshes this automatically every day
          (06:00 UTC) and on startup. No synthetic or scraped fare data is used.
        </p>
      </Card>
    </div>
  )
}

function TabBar({ tabs, active, onChange }: { tabs: { key: string; label: string }[]; active: string; onChange: (k: any) => void }) {
  return (
    <div className="flex border-b border-slate-200 mb-6">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            active === t.key
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}