import type { ReactNode } from 'react'

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function StatCard({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'up' | 'down' | 'neutral'
}) {
  const toneClass = tone === 'up' ? 'text-red-600' : tone === 'down' ? 'text-emerald-600' : 'text-ink'
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${toneClass}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  )
}

export function Card({ title, children, className = '' }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`bg-white border border-slate-200 rounded-lg p-5 ${className}`}>
      {title && <h2 className="text-sm font-semibold text-ink mb-3">{title}</h2>}
      {children}
    </section>
  )
}

const SOURCE_LABEL_STYLES: Record<string, string> = {
  LIVE_SCRAPE: 'bg-emerald-100 text-emerald-800',
  PUBLIC_DATASET: 'bg-blue-100 text-blue-800',
  DEMO_SIMULATED: 'bg-amber-100 text-amber-800',
  SOURCE_UNAVAILABLE: 'bg-red-100 text-red-800',
}

export function SourceBadge({ sourceType }: { sourceType: string }) {
  const style = SOURCE_LABEL_STYLES[sourceType] ?? 'bg-slate-100 text-slate-700'
  return (
    <span className={`text-[11px] font-bold tracking-wide px-2 py-0.5 rounded ${style}`}>
      {sourceType.replace('_', ' ')}
    </span>
  )
}

const QUALITY_STYLES: Record<string, string> = {
  VALID: 'bg-emerald-100 text-emerald-800',
  SUSPICIOUS: 'bg-amber-100 text-amber-800',
  INVALID: 'bg-red-100 text-red-800',
  UNAVAILABLE: 'bg-slate-200 text-slate-700',
}

export function QualityBadge({ status }: { status: string }) {
  const style = QUALITY_STYLES[status] ?? 'bg-slate-100 text-slate-700'
  return <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${style}`}>{status}</span>
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="text-sm text-muted py-10 text-center">{label}</div>
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-4">
      Couldn't load this data: {message}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <div className="text-sm text-muted py-10 text-center">{message}</div>
}
