import type { ReactNode } from 'react'

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-7">
      <div className="animate-fade-in-up">
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1.5">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function StatCard({
  label,
  value,
  sub,
  tone = 'neutral',
  icon,
  accent = false,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'up' | 'down' | 'neutral'
  icon?: ReactNode
  accent?: boolean
}) {
  const toneClass =
    tone === 'up' ? 'text-rose-400' : tone === 'down' ? 'text-emerald-400' : accent ? 'text-white' : 'text-ink'
  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-line bg-surface p-4 shadow-card transition-colors ${
        accent ? 'border-brand-700/40' : ''
      }`}
    >
      {accent && <div className="absolute inset-x-0 top-0 h-0.5 bg-brand-gradient" />}
      <div className="relative flex items-start justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{label}</div>
          <div className={`mt-2 text-[26px] font-bold leading-tight ${toneClass}`}>{value}</div>
          {sub && <div className="mt-1.5 text-xs text-muted">{sub}</div>}
        </div>
        {icon && <div className="text-brand-400 opacity-80">{icon}</div>}
      </div>
    </div>
  )
}

export function Card({ title, children, className = '', action }: { title?: ReactNode; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <section className={`rounded-xl border border-line bg-surface shadow-card ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between px-5 pt-4 pb-2">
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          {action}
        </header>
      )}
      <div className="px-5 pb-5">{children}</div>
    </section>
  )
}

const SOURCE_LABEL_STYLES: Record<string, string> = {
  LIVE_SCRAPE: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  PUBLIC_DATASET: 'bg-brand-500/15 text-brand-300 border border-brand-500/30',
  DEMO_SIMULATED: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  SOURCE_UNAVAILABLE: 'bg-rose-500/15 text-rose-300 border border-rose-500/30',
}

export function SourceBadge({ sourceType }: { sourceType: string }) {
  const style = SOURCE_LABEL_STYLES[sourceType] ?? 'bg-slate-500/15 text-slate-300 border border-slate-500/30'
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-bold tracking-wide px-2.5 py-1 rounded-full ${style}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {sourceType.replace(/_/g, ' ')}
    </span>
  )
}

const QUALITY_STYLES: Record<string, string> = {
  VALID: 'bg-emerald-500/15 text-emerald-300',
  SUSPICIOUS: 'bg-amber-500/15 text-amber-300',
  INVALID: 'bg-rose-500/15 text-rose-300',
  UNAVAILABLE: 'bg-slate-500/20 text-slate-300',
}

export function QualityBadge({ status }: { status: string }) {
  const style = QUALITY_STYLES[status] ?? 'bg-slate-500/15 text-slate-300'
  return <span className={`inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full ${style}`}>{status}</span>
}

export function Skeleton({ className = 'h-4' }: { className?: string }) {
  return <div className={`animate-pulse-soft rounded-md bg-lineSoft ${className}`} />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="space-y-4 py-6" role="status" aria-label={label}>
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
      <Skeleton className="h-64 rounded-xl" />
      <p className="sr-only">{label}</p>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4">
      <div className="text-sm text-rose-200">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded-lg border border-rose-500/40 px-3 py-1.5 text-xs font-semibold text-rose-200 hover:bg-rose-500/20 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-lineSoft text-muted">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 13.5H9m4.06-9.19-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 3v18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 21V5.625a1.5 1.5 0 0 0-.44-1.06l-2.12-2.12m-5.13-1.06v4.94a1.5 1.5 0 0 0 1.5 1.5h4.94" />
        </svg>
      </div>
      <p className="max-w-sm text-sm text-muted">{message}</p>
    </div>
  )
}

export function TrendPill({ value, suffix = '%' }: { value: number | null | undefined; suffix?: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="text-xs text-muted">—</span>
  }
  const up = value >= 0
  const cls = up ? 'text-rose-400 bg-rose-500/10 border-rose-500/25' : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25'
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full border px-2 py-0.5 text-xs font-bold tabular-nums ${cls}`}>
      {up ? '+' : ''}
      {value.toFixed(2)}
      {suffix}
      <span aria-hidden>{up ? '↗' : '↘'}</span>
    </span>
  )
}

export function InfoRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6 py-2">
      <span className="text-muted text-sm">{label}</span>
      <span className="text-sm font-medium text-ink text-right">{children}</span>
    </div>
  )
}