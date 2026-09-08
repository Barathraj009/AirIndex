import { useState, useEffect } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import { PageHeader, Card, StatCard, LoadingState, ErrorState } from '../components/ui'
import type { CpiSimulationResponse } from '../types'

export default function CpiAugmentation() {
  const [airfareWeight, setAirfareWeight] = useState<number>(0.20) // in percentage (0.20%)
  const [transportWeight, setTransportWeight] = useState<number>(8.59) // in percentage (8.59%)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [simulationData, setSimulationData] = useState<CpiSimulationResponse | null>(null)

  const runSimulation = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post<CpiSimulationResponse>('/cpi/simulate', {
        airfare_weight_in_cpi: airfareWeight / 100.0,
        transport_group_weight: transportWeight / 100.0,
      })
      setSimulationData(res)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runSimulation()
  }, [])

  return (
    <div>
      <PageHeader
        title="MoSPI CPI Augmentation Simulator"
        subtitle="Simulate real-time integration of Airfare Price Index (APIx) into India's official Consumer Price Index (Base 2012=100)"
      />

      {/* Simulator Controls Card */}
      <Card className="mb-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1 w-full">
            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <span className="font-semibold text-slate-700">Airfare Weight in Headline CPI</span>
                <span className="font-mono font-bold text-blue-600">{airfareWeight.toFixed(2)}%</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="1.50"
                step="0.05"
                value={airfareWeight}
                onChange={(e) => setAirfareWeight(parseFloat(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer"
              />
              <span className="text-[11px] text-muted">MoSPI estimated basket weight (~0.20% All-India)</span>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <span className="font-semibold text-slate-700">Transport & Comm. Group Weight</span>
                <span className="font-mono font-bold text-blue-600">{transportWeight.toFixed(2)}%</span>
              </div>
              <input
                type="range"
                min="4.00"
                max="15.00"
                step="0.25"
                value={transportWeight}
                onChange={(e) => setTransportWeight(parseFloat(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer"
              />
              <span className="text-[11px] text-muted">Official All-India weight (8.59%)</span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <button
              onClick={runSimulation}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-5 py-2.5 rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {loading ? 'Simulating…' : '⚡ Re-simulate CPI Impact'}
            </button>
            <button
              onClick={() => {
                setAirfareWeight(0.20)
                setTransportWeight(8.59)
              }}
              className="text-[11px] text-slate-500 hover:text-slate-800 text-center"
            >
              Reset to Defaults
            </button>
          </div>
        </div>
      </Card>

      {error && <ErrorState message={error} />}

      {loading && !simulationData && <LoadingState label="Computing CPI augmentation simulation…" />}

      {simulationData && (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Mean Inflation Delta"
              value={`${simulationData.mean_headline_delta_bps > 0 ? '+' : ''}${simulationData.mean_headline_delta_bps.toFixed(1)} bps`}
              sub="Average deviation in headline CPI"
              tone={simulationData.mean_headline_delta_bps >= 0 ? 'up' : 'down'}
            />
            <StatCard
              label="Peak Headline Delta"
              value={`±${simulationData.max_headline_delta_bps.toFixed(1)} bps`}
              sub="Max surge-period impact"
              tone="up"
            />
            <StatCard
              label="Reporting Lag Reduction"
              value={`~${simulationData.lag_reduction_days_est} Days`}
              sub="Faster shock transmission vs surveys"
              tone="down"
            />
            <StatCard
              label="Transport Weight Impact"
              value={`${(simulationData.airfare_weight_pct / simulationData.transport_weight_pct * 100).toFixed(1)}%`}
              sub="Air share of Transport basket"
            />
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Chart 1: Headline CPI */}
            <Card title="Headline CPI (Base 2012=100) — Official vs Augmented">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={simulationData.points}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="official_general_cpi" name="Official Headline CPI" stroke="#64748b" strokeDasharray="4 4" strokeWidth={2} />
                  <Line type="monotone" dataKey="augmented_general_cpi" name="APIx-Augmented CPI" stroke="#1d4ed8" strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-muted mt-2">
                Demonstrates how high-frequency airfare price dynamics immediately reflect in the overall headline index.
              </p>
            </Card>

            {/* Chart 2: Transport Subgroup */}
            <Card title="Transport Subgroup Index — Official vs APIx-Augmented">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={simulationData.points}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="official_transport_cpi" name="Official Transport CPI" stroke="#94a3b8" strokeDasharray="4 4" strokeWidth={2} />
                  <Line type="monotone" dataKey="augmented_transport_cpi" name="APIx-Augmented Transport" stroke="#059669" strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-muted mt-2">
                Captures peak travel fare increases that are historically smoothed out by quarterly manual physical surveys.
              </p>
            </Card>
          </div>

          {/* Chart 3: Headline Inflation Delta Bar Chart */}
          <Card title="Headline Inflation Delta by Period (Basis Points)" className="mb-6">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={simulationData.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis unit=" bps" tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(2)} bps`, 'Headline Inflation Delta']} />
                <Bar dataKey="inflation_delta_bps" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Policy Assessment */}
          <Card title="MoSPI Policy Assessment & Methodology Insights">
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-700 space-y-2">
              <p className="font-semibold text-slate-900">{simulationData.policy_summary}</p>
              <p>
                <strong>Key Finding for Statistical Officers:</strong> The traditional manual airfare collection process introduces up to 45–60 days of lag in official CPI releases. By integrating automated daily/weekly APIx observations, MoSPI can accurately capture high-volatility festival travel shocks (e.g. Diwali, Summer holidays) in real time without waiting for retrospective quarterly airline survey returns.
              </p>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
