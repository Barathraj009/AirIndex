import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, SourceBadge, EmptyState } from '../components/ui'
import type { CpiAirfareIndex, CpiAirfareTrend } from '../types'

export default function Dashboard() {
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=12')

  if (current.loading) return <LoadingState label="Loading CPI data..." />
  if (current.error) return <ErrorState message={current.error} />
  if (!current.data) return null

  const data = current.data
  const trendData = trend.data?.series ?? []

  if (!data.available) {
    return (
      <div>
        <PageHeader
          title="Airfare Price Index"
          subtitle="MoSPI CPI 07.3.3.1 · Base 2024=100"
          action={<SourceBadge sourceType="PUBLIC_DATASET" />}
        />
        <Card>
          <EmptyState message="Awaiting MoSPI CPI airfare data. The backend fetches it from esankhyiki.mospi.gov.in shortly after startup." />
        </Card>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Airfare Price Index"
        subtitle={`MoSPI CPI 07.3.3.1 · Base ${data.base_year}`}
        action={<SourceBadge sourceType="PUBLIC_DATASET" />}
      />

      {/* Primary Index Card */}
      <div className="bg-blue-600 text-white rounded-lg px-5 py-4 mb-6">
        <div className="text-xs font-bold uppercase tracking-wide opacity-80 mb-1">
          Current Airfare CPI Index
        </div>
        <div className="text-3xl font-bold">{data.airfare_index!.toFixed(2)}</div>
        <div className="text-xs opacity-80 mt-1">
          Period: {data.period} · Source: MoSPI (esankhyiki.mospi.gov.in)
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Airfare CPI"
          value={data.airfare_index!.toFixed(2)}
          sub={`Code ${data.cpi_code || '07.3.3.1'}`}
        />
        <StatCard
          label="Transport CPI"
          value={data.transport_index?.toFixed(2) ?? 'N/A'}
          sub="Division 07"
        />
        <StatCard
          label="YoY Inflation"
          value={data.inflation_yoy !== null ? `${data.inflation_yoy.toFixed(2)}%` : 'N/A'}
          tone={data.inflation_yoy !== null && data.inflation_yoy > 0 ? 'up' : 'down'}
          sub="Year-over-year"
        />
      </div>

      {/* Trend Chart */}
      {trendData.length > 0 && (
        <Card title="CPI Airfare Index Trend" className="mb-6">
          <p className="text-xs text-muted mb-3">
            Monthly CPI values from MoSPI (base 2024=100)
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="airfare_index"
                stroke="#1d4ed8"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="Airfare CPI"
              />
              <Line
                type="monotone"
                dataKey="transport_index"
                stroke="#64748b"
                strokeWidth={1}
                dot={{ r: 2 }}
                name="Transport CPI"
              />
              <Line
                type="monotone"
                dataKey="general_index"
                stroke="#94a3b8"
                strokeWidth={1}
                dot={{ r: 2 }}
                name="General CPI"
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Data Source Info */}
      <Card title="Data Source" className="mb-6">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Source</span>
            <span className="font-medium">Ministry of Statistics and Programme Implementation</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Portal</span>
            <a href="https://esankhyiki.mospi.gov.in" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              esankhyiki.mospi.gov.in
            </a>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">CPI Code</span>
            <span className="font-medium">07.3.3.1 - Passenger transport by air, domestic</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Base Year</span>
            <span className="font-medium">{data.base_year}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Last Fetched</span>
            <span className="font-medium">
              {data.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'N/A'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  )
}