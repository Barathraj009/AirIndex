import { useEffect, useRef, useState } from 'react'

interface Datum {
  label: string
  value: number
  color?: string
}

export default function WebGL3DChart({ data, height = 340, valueFormatter }: { data: Datum[]; height?: number; valueFormatter?: (v: number) => string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const [echartMod, setEchartMod] = useState<any>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([import('echarts'), import('echarts-gl')])
      .then(([echarts]) => {
        if (!cancelled) setEchartMod(echarts)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!echartMod || !ref.current) return
    const chart = echartMod.init(ref.current)
    const dim = window.devicePixelRatio > 1 ? 2 : 1

    const labels = data.map((d) => d.label)
    const values = data.map((d) => d.value)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const pad = Math.max(2, (max - min) * 0.12)
    const domain: [number, number] = [Math.floor(min - pad), Math.ceil(max + pad)]

    chart.setOption({
      tooltip: {
        formatter: (p: any) => `${labels[p.value[0]] ?? ''}<br/>${valueFormatter ? valueFormatter(p.value[2]) : p.value[2]}`,
      },
      grid3D: {
        boxWidth: 120,
        boxDepth: 40,
        boxHeight: 90,
        viewControl: { autoRotate: true, autoRotateSpeed: 6, distance: 190 },
        light: { main: { intensity: 1.2 }, ambient: { intensity: 0.4 } },
        axisPointer: { show: true },
        xAxis3D: { type: 'category', data: labels, axisLabel: { interval: Math.max(0, Math.floor(labels.length / 10) - 1), fontSize: 10 } },
        yAxis3D: { type: 'value', min: domain[0], max: domain[1] },
        zAxis3D: { type: 'category', data: ['.', ''], show: false },
      },
      series: [
        {
          type: 'bar3D',
          data: data.map((d, i) => [i, d.value, 0] as [number, number, number]),
          shading: 'lambert',
          itemStyle: {
            color: (p: any) => data[p.dataIndex]?.color ?? '#1471e8',
          },
          emphasis: { itemStyle: { color: '#f59e0b' } },
          label: {
            show: false,
            textStyle: { fontSize: 10, color: '#0f172a' },
            formatter: (p: any) => (valueFormatter ? valueFormatter(p.value[1]) : String(p.value[1])),
          },
        },
      ],
    }, dim)
    chart.resize()

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [echartMod, data, valueFormatter])

  if (failed) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-line text-xs text-muted">
        Interactive 3D (WebGL) could not load. Try the 2D or classic 3D view instead.
      </div>
    )
  }

  return (
    <div className="relative">
      <div ref={ref} style={{ width: '100%', height }} />
      <p className="mt-1 text-center text-[10px] text-muted">Drag to rotate · scroll to zoom · auto-rotates</p>
    </div>
  )
}