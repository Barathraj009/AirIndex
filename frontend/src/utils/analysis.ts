import type { CpiAirfareTrendPoint } from '../types'

export interface SeasonalityRow {
  month: string
  avgIndex: number
  deviationPct: number
  count: number
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function movingAverage(values: number[], window: number): (number | null)[] {
  return values.map((_, i) => {
    if (i < window - 1) return null
    const slice = values.slice(i - window + 1, i + 1)
    return slice.reduce((a, b) => a + b, 0) / slice.length
  })
}

export function computeSeasonality(series: CpiAirfareTrendPoint[]): SeasonalityRow[] {
  const buckets: Record<number, { sum: number; count: number }> = {}
  const yearSums: Record<string, { sum: number; count: number }> = {}
  for (const p of series) {
    const parts = p.period.split('-')
    const month = parseInt(parts[1], 10)
    if (!month) continue
    if (!buckets[month]) buckets[month] = { sum: 0, count: 0 }
    buckets[month].sum += p.airfare_index
    buckets[month].count += 1
    if (!yearSums[parts[0]]) yearSums[parts[0]] = { sum: 0, count: 0 }
    yearSums[parts[0]].sum += p.airfare_index
    yearSums[parts[0]].count += 1
  }
  const yearMean: Record<string, number> = {}
  for (const [year, v] of Object.entries(yearSums)) yearMean[year] = v.sum / v.count

  // De-trend: measure each observation against its own calendar year's mean,
  // so the calendar-month pattern is not dominated by the index level rising
  // from ~100 (2024) to ~126 (2026).
  const devBuckets: Record<number, number[]> = {}
  for (const p of series) {
    const parts = p.period.split('-')
    const month = parseInt(parts[1], 10)
    const ym = yearMean[parts[0]]
    if (!month || !ym) continue
    if (!devBuckets[month]) devBuckets[month] = []
    devBuckets[month].push(((p.airfare_index - ym) / ym) * 100)
  }

  const rows: SeasonalityRow[] = []
  for (let m = 1; m <= 12; m++) {
    const b = buckets[m]
    if (!b || b.count === 0) {
      rows.push({ month: MONTH_NAMES[m - 1], avgIndex: 0, deviationPct: 0, count: 0 })
      continue
    }
    const avgIndex = b.sum / b.count
    const devs = devBuckets[m] ?? []
    const deviationPct = devs.length ? devs.reduce((a, b) => a + b, 0) / devs.length : 0
    rows.push({ month: MONTH_NAMES[m - 1], avgIndex, deviationPct, count: b.count })
  }
  return rows
}

export interface VolatilityBucket {
  label: string
  stdDev: number
  level: 'CALM' | 'MODERATE' | 'ELEVATED'
}

export function computeVolatility(series: CpiAirfareTrendPoint[]): VolatilityBucket[] {
  const mom = series
    .map((p, i) => {
      if (i === 0) return null
      const prev = series[i - 1].airfare_index
      if (!prev) return null
      return ((p.airfare_index - prev) / prev) * 100
    })
    .filter((v): v is number => v !== null && Number.isFinite(v))

  const std = (vals: number[]) => {
    if (vals.length < 2) return 0
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length
    return Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (vals.length - 1))
  }

  const level = (v: number): VolatilityBucket['level'] =>
    v >= 2.0 ? 'ELEVATED' : v >= 1.0 ? 'MODERATE' : 'CALM'

  const round2 = (v: number) => Math.round(v * 100) / 100

  return [
    { label: '3-month', stdDev: round2(std(mom.slice(-3))), level: level(std(mom.slice(-3))) },
    { label: '6-month', stdDev: round2(std(mom.slice(-6))), level: level(std(mom.slice(-6))) },
    { label: '12-month', stdDev: round2(std(mom.slice(-12))), level: level(std(mom.slice(-12))) },
  ]
}

export function fmt(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '\u2014'
  return v.toFixed(digits)
}