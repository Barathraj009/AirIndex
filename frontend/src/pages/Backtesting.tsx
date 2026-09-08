import { useState } from 'react'
import type { ReactNode } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import { PageHeader, Card, StatCard, EmptyState } from '../components/ui'
import type { BacktestResult } from '../types'

export default function Backtesting() {
  const [startPeriod, setStartPeriod] = useState('2026-01')
  const [endPeriod, setEndPeriod] = useState('2026-06')
  const [referenceDataset, setReferenceDataset] = useState('DEMO_REFERENCE')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    try {
      const res = await api.post<BacktestResult>('/backtesting/run', {
        start_period: startPeriod,
        end_period: endPeriod,
        reference_dataset: referenceDataset,
      })
      setResult(res)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <PageHeader title="Backtesting" subtitle="Compare the calculated APIx against a reference fare dataset" />

      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-4 text-sm">
          <Field label="Start period">
            <input
              type="month"
              value={startPeriod}
              onChange={(e) => setStartPeriod(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1.5"
            />
          </Field>
          <Field label="End period">
            <input
              type="month"
              value={endPeriod}
              onChange={(e) => setEndPeriod(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1.5"
            />
          </Field>
          <Field label="Reference dataset">
            <select
              value={referenceDataset}
              onChange={(e) => setReferenceDataset(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1.5"
            >
              <option value="DGCA_MONTHLY_AVG">DGCA_MONTHLY_AVG</option>
              <option value="DEMO_REFERENCE">DEMO_REFERENCE (demonstration only)</option>
            </select>
          </Field>
          <button
            onClick={handleRun}
            disabled={running}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded disabled:opacity-50"
          >
            {running ? 'Running…' : 'Run backtest'}
          </button>
        </div>
      </Card>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-4 mb-4">{error}</div>}

      {result && !result.reference_available && (
        <Card>
          <EmptyState
            message={
              result.note ??
              'Reference data unavailable for this period/dataset. Nothing is fabricated — load real DGCA data or use DEMO_REFERENCE.'
            }
          />
        </Card>
      )}

      {result && result.reference_available && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard label="MAE" value={result.mae?.toFixed(3) ?? '—'} />
            <StatCard label="RMSE" value={result.rmse?.toFixed(3) ?? '—'} />
            <StatCard label="MAPE" value={result.mape !== null ? `${result.mape.toFixed(2)}%` : '—'} />
            <StatCard label="Correlation" value={result.correlation?.toFixed(3) ?? '—'} />
          </div>

          <Card title="APIx vs reference">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={result.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="actual" name="APIx" stroke="#1d4ed8" strokeWidth={2} />
                <Line type="monotone" dataKey="reference" name="Reference" stroke="#64748b" strokeDasharray="5 3" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}

      {!result && !error && (
        <Card>
          <EmptyState message="Choose a period range and reference dataset, then run the backtest." />
        </Card>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-muted">{label}</span>
      {children}
    </label>
  )
}
