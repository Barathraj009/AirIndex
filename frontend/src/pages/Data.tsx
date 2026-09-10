import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, StatCard, LoadingState, ErrorState, EmptyState, SourceBadge, InfoRow, TrendPill } from '../components/ui'
import { TabBar } from '../components/Tabs'
import type { CpiAirfareTrend, CpiAirfareIndex } from '../types'

type DataTab = 'observations' | 'source'

export default function Data() {
  const [tab, setTab] = useState<DataTab>('observations')

  return (
    <div>
      <PageHeader title="Data" subtitle="CPI airfare observations from MoSPI" />
      <TabBar
        tabs={[
          { key: 'observations', label: 'CPI Observations' },
          { key: 'source', label: 'Source & Freshness' },
        ]}
        active={tab}
        onChange={(k) => setTab(k as DataTab)}
      />

      <div key={tab} className="animate-fade-in-up">
        {tab === 'observations' && <ObservationsTab />}
        {tab === 'source' && <SourceTab />}
      </div>
    </div>
  )
}

function ObservationsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=36')
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')

  if (trend.loading) return <LoadingState label="Loading CPI observations..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="No CPI observations yet. The backend fetches MoSPI data shortly after startup." />
      </Card>
    )
  }

  const rows = data.map((p, i) => {
    const prev = i > 0 ? data[i - 1].airfare_index : null
    const momPct = prev && prev > 0 ? ((p.airfare_index - prev) / prev) * 100 : null
    return { ...p, mom_pct: momPct }
  })

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Months available" value={rows.length} sub="of published MoSPI history" />
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
              <tr className="text-left text-muted border-b border-line bg-raised/60">
                <th className="py-2.5 px-3 font-medium">Period</th>
                <th className="py-2.5 px-3 text-right font-medium">Airfare CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Transport CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">General CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">MoM %</th>
                <th className="py-2.5 px-3 text-right font-medium">YoY %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.period} className="border-b border-lineSoft hover:bg-raised/40 transition-colors">
                  <td className="py-2 px-3 font-medium text-ink">{p.period}</td>
                  <td className="py-2 px-3 text-right tabular-nums">{p.airfare_index.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right tabular-nums text-muted">
                    {p.transport_index != null ? p.transport_index.toFixed(2) : '\u2014'}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums text-muted">
                    {p.general_index != null ? p.general_index.toFixed(2) : '\u2014'}
                  </td>
                  <td className="py-2 px-3 text-right"><TrendPill value={p.mom_pct} /></td>
                  <td className="py-2 px-3 text-right"><TrendPill value={p.inflation_yoy} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-muted">
          Source: MoSPI Consolidated CPI (code 07.3.3.1, base 2024=100) via esankhyiki.mospi.gov.in.
        </p>
      </Card>
    </div>
  )
}

function SourceTab() {
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')

  if (current.loading) return <LoadingState label="Loading source info..." />
  if (current.error) return <ErrorState message={current.error} onRetry={current.refetch} />

  const data = current.data

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="Primary data source">
        <div className="flex items-center gap-2 pb-3">
          <SourceBadge sourceType="PUBLIC_DATASET" />
          <span className="text-xs text-muted">authoritative &amp; free-to-use</span>
        </div>
        <div className="divide-y divide-lineSoft">
          <InfoRow label="Publisher">Ministry of Statistics and Programme Implementation (MoSPI)</InfoRow>
          <InfoRow label="Portal">
            <a href="https://esankhyiki.mospi.gov.in" target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline">
              esankhyiki.mospi.gov.in
            </a>
          </InfoRow>
          <InfoRow label="CPI code">07.3.3.1 · Passenger transport by air, domestic</InfoRow>
          <InfoRow label="Base year">{data?.base_year ?? '2024=100'}</InfoRow>
          <InfoRow label="Release cadence">Monthly (published ~12th of following month)</InfoRow>
        </div>
      </Card>

      <Card title="Pipeline & freshness">
        <div className="divide-y divide-lineSoft">
          <InfoRow label="Last fetched">
            {data?.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'Not yet fetched'}
          </InfoRow>
          <InfoRow label="Backend">Fetch from api.mospi.gov.in via SSL with legacy TLS support</InfoRow>
          <InfoRow label="Refresh schedule">Daily at 06:00 UTC + on startup</InfoRow>
        </div>
        <p className="mt-4 rounded-lg border border-brand-500/25 bg-brand-500/10 px-3 py-2.5 text-xs leading-relaxed text-brand-200">
          The APIx platform ingests the official MoSPI Consolidated CPI series for the air transport
          sub-component. No synthetic or scraped fare data is used.
        </p>
      </Card>
    </div>
  )
}