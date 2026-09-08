import { Link } from 'react-router-dom'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState } from '../components/ui'
import type { DashboardSummary, DataQualitySummary, FareAnomaly } from '../types'

export default function Overview() {
  const summary = useApiQuery<DashboardSummary>('/dashboard/summary')
  const quality = useApiQuery<DataQualitySummary>('/data-quality/summary')
  const anomaliesQuery = useApiQuery<{ total_anomalies: number; anomalies: FareAnomaly[] }>('/analytics/anomalies')

  if (summary.loading) return <LoadingState label="Loading dashboard…" />
  if (summary.error) return <ErrorState message={summary.error} />
  if (!summary.data) return null

  const { index, n_routes_tracked, n_airlines_tracked, current_period, base_period } = summary.data

  const topContributors = Object.entries(index.route_contributions)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 6)

  const anomalies = anomaliesQuery.data?.anomalies ?? []

  return (
    <div>
      <PageHeader
        title="AirIndex India Overview"
        subtitle={`Airfare Price Index snapshot — base ${base_period}, current period ${current_period}`}
        action={
          <div className="flex gap-2">
            <a
              href="/api/exports/monthly-bulletin"
              target="_blank"
              rel="noreferrer"
              className="text-xs bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded font-medium shadow-sm transition"
            >
              📄 Export Monthly Bulletin
            </a>
            <Link
              to="/cpi-simulator"
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded font-medium shadow-sm transition"
            >
              ⚡ CPI Augmentation
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Current APIx" value={index.index_value.toFixed(2)} sub={`Base = 100.0`} />
        <StatCard
          label="Change vs base"
          value={`${index.change_from_base_pct >= 0 ? '+' : ''}${index.change_from_base_pct.toFixed(2)}%`}
          tone={index.change_from_base_pct >= 0 ? 'up' : 'down'}
          sub={`as of ${index.as_of_period}`}
        />
        <StatCard label="Routes tracked" value={n_routes_tracked} sub={`${index.n_observations_used.toLocaleString()} obs. used`} />
        <StatCard label="Airlines tracked" value={n_airlines_tracked} sub={index.methodology_version} />
      </div>

      {/* Surge & Price Spike Alerts Card */}
      {anomalies.length > 0 && (
        <Card title="⚡ Live Surge Pricing & Price Gouging Alerts" className="mb-6 border-amber-200 bg-amber-50/40">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {anomalies.slice(0, 3).map((anom, idx) => (
              <div key={idx} className="bg-white border border-amber-200 rounded-lg p-3 shadow-xs">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-slate-800 text-xs">{anom.route}</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    anom.severity === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {anom.severity} SURGE
                  </span>
                </div>
                <p className="text-xs text-slate-600 font-semibold mb-1">+{anom.deviation_pct}% vs Route Median</p>
                <p className="text-[11px] text-muted">{anom.description}</p>
                <div className="mt-2 text-[10px] text-slate-500 flex justify-between">
                  <span>Carrier: {anom.airline}</span>
                  <span>{anom.booking_window_days ? `T+${anom.booking_window_days}` : anom.travel_date}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card title="Top route contributors to index change" className="lg:col-span-2">
          <div className="space-y-2">
            {topContributors.map(([route, val]) => (
              <div key={route} className="flex items-center gap-3 text-sm">
                <div className="w-20 font-medium">{route}</div>
                <div className="flex-1 h-3 bg-slate-100 rounded relative overflow-hidden">
                  <div
                    className={`absolute h-3 ${val >= 0 ? 'bg-red-500' : 'bg-emerald-500'}`}
                    style={{
                      width: `${Math.min(100, Math.abs(val) * 20)}%`,
                      left: val >= 0 ? '50%' : undefined,
                      right: val < 0 ? '50%' : undefined,
                    }}
                  />
                </div>
                <div className={`w-16 text-right ${val >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                  {val.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-4 mt-3 text-xs">
            <Link to="/routes" className="text-blue-600 hover:underline">
              View full route analysis →
            </Link>
            <Link to="/geospatial-map" className="text-blue-600 hover:underline">
              Explore Geospatial Corridor Map →
            </Link>
          </div>
        </Card>

        <Card title="Data quality snapshot">
          {quality.data ? (
            <div className="space-y-2 text-sm">
              <Row label="Valid" value={quality.data.valid} tone="text-emerald-600" />
              <Row label="Suspicious" value={quality.data.suspicious} tone="text-amber-600" />
              <Row label="Invalid" value={quality.data.invalid} tone="text-red-600" />
              <Row label="Unavailable" value={quality.data.unavailable} tone="text-slate-500" />
              <div className="pt-2 text-xs text-muted">{quality.data.valid_pct}% of rows valid</div>
              <Link to="/quality" className="text-xs text-blue-600 inline-block pt-1">
                View data quality detail →
              </Link>
            </div>
          ) : (
            <LoadingState />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="MoSPI CPI Augmentation Engine">
          <p className="text-xs text-slate-600 mb-3">
            Simulate how the real-time APIx index integrates into India's official Consumer Price Index Transport subgroup to reduce survey publication lag by ~45 days.
          </p>
          <Link to="/cpi-simulator" className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded font-medium inline-block hover:bg-blue-100">
            Open CPI Policy Simulator →
          </Link>
        </Card>

        <Card title="Methodology & DGCA Calibration">
          <p className="text-xs text-slate-600 mb-3">
            APIx is a modified Laspeyres route-weighted index calibrated with DGCA passenger traffic volume and median booking-window aggregations.
          </p>
          <Link to="/methodology" className="text-xs bg-slate-100 text-slate-700 px-3 py-1.5 rounded font-medium inline-block hover:bg-slate-200">
            Read Methodology Specification →
          </Link>
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={`font-semibold ${tone}`}>{value.toLocaleString()}</span>
    </div>
  )
}
