import { useMemo } from 'react'

export interface IsometricDatum {
  label: string
  value: number
  color?: string
}

interface IsometricChartProps {
  data: IsometricDatum[]
  valueFormatter?: (v: number) => string
  height?: number
  className?: string
  upColor?: string
  downColor?: string
}

function shade(hex: string, amount: number): string {
  const n = hex.replace('#', '')
  const r = Math.max(0, Math.min(255, parseInt(n.slice(0, 2), 16) + amount))
  const g = Math.max(0, Math.min(255, parseInt(n.slice(2, 4), 16) + amount))
  const b = Math.max(0, Math.min(255, parseInt(n.slice(4, 6), 16) + amount))
  return `rgb(${r}, ${g}, ${b})`
}

export default function IsometricChart({
  data,
  valueFormatter = (v) => v.toFixed(2),
  height = 320,
  className = '',
  upColor = '#1471e8',
  downColor = '#10b981',
}: IsometricChartProps) {
  const maxAbs = useMemo(() => data.reduce((m, d) => Math.max(m, Math.abs(d.value)), 0) || 1, [data])
  const plotH = height - 72
  const colW = 40
  const barW = 24
  const depth = 14
  const totalW = Math.max(240, data.length * colW + 64)

  if (data.length === 0) {
    return <div className="py-12 text-center text-sm text-muted">No data</div>
  }

  return (
    <div className={`overflow-x-auto ${className}`}>
      <div className="relative mx-auto" style={{ width: totalW, height }}>
        <div className="absolute left-5 right-5 bottom-8 border-t-2 border-slate-200" aria-hidden />
        {data.map((d, i) => {
          const neg = d.value < 0
          const h = Math.max(6, (Math.abs(d.value) / maxAbs) * (plotH - 24))
          const base = d.color ?? (neg ? downColor : upColor)
          const x = 32 + i * colW
          return (
            <div key={i} className="absolute bottom-8" style={{ left: x }} title={`${d.label}: ${valueFormatter(d.value)}`} aria-label={`${d.label}: ${valueFormatter(d.value)}`}>
              <div className="relative transition-transform hover:-translate-y-0.5" style={{ width: barW, height: h }}>
                <div
                  className="absolute left-full top-0"
                  style={{ width: depth, height: h, transformOrigin: 'top left', transform: 'skewY(-45deg)', background: `linear-gradient(180deg, ${shade(base, 20)}, ${shade(base, -14)})` }}
                  aria-hidden
                />
                <div
                  className="absolute bottom-full left-0"
                  style={{ width: barW, height: depth, transformOrigin: 'bottom right', transform: 'skewX(-45deg)', background: shade(base, 34) }}
                  aria-hidden
                />
                <div
                  className="absolute inset-0"
                  style={{ background: `linear-gradient(180deg, ${shade(base, 18)}, ${base} 55%, ${shade(base, -10)})`, borderTopLeftRadius: 3, borderTopRightRadius: 3, boxShadow: 'inset 0 -8px 14px rgba(255,255,255,0.18), inset 0 1px 0 rgba(255,255,255,0.35)' }}
                />
              </div>
              <div className="absolute left-1/2 top-full mt-3 w-[38px] -translate-x-1/2 text-center text-[10px] font-medium text-slate-500">{d.label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}