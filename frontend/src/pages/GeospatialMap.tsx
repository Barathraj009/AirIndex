import { useState, useMemo } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, StatCard } from '../components/ui'
import type { IndexResult, Route } from '../types'

interface AirportCoord {
  code: string
  name: string
  x: number
  y: number
}

const AIRPORTS: Record<string, AirportCoord> = {
  DEL: { code: 'DEL', name: 'Delhi (IGI)', x: 330, y: 170 },
  BOM: { code: 'BOM', name: 'Mumbai (CSMIA)', x: 220, y: 410 },
  BLR: { code: 'BLR', name: 'Bengaluru (KIA)', x: 300, y: 560 },
  MAA: { code: 'MAA', name: 'Chennai (MAA)', x: 360, y: 560 },
  CCU: { code: 'CCU', name: 'Kolkata (NSCBIA)', x: 550, y: 310 },
  HYD: { code: 'HYD', name: 'Hyderabad (RGIA)', x: 340, y: 440 },
  PNQ: { code: 'PNQ', name: 'Pune (PNQ)', x: 245, y: 435 },
  AMD: { code: 'AMD', name: 'Ahmedabad (SVPIA)', x: 210, y: 300 },
  GAU: { code: 'GAU', name: 'Guwahati (LGBIA)', x: 670, y: 240 },
  COK: { code: 'COK', name: 'Kochi (CIAL)', x: 275, y: 640 },
  GOI: { code: 'GOI', name: 'Goa (Dabolim/MOPA)', x: 235, y: 500 },
}

export default function GeospatialMap() {
  const indexQuery = useApiQuery<IndexResult>('/index/current')
  const routesQuery = useApiQuery<Route[]>('/routes')

  const [selectedRouteKey, setSelectedRouteKey] = useState<string>('DEL-BOM')
  const [selectedAirport, setSelectedAirport] = useState<string | null>(null)

  const routeFares = indexQuery.data?.route_fares ?? {}

  const activeCorridors = useMemo(() => {
    const list: Array<{
      key: string
      origin: string
      dest: string
      change_pct: number
      relative: number
      base_fare: number
      current_fare: number
      weight: number
      from: AirportCoord
      to: AirportCoord
    }> = []

    Object.entries(routeFares).forEach(([rKey, detail]) => {
      const [orig, dest] = rKey.split('-')
      const from = AIRPORTS[orig]
      const to = AIRPORTS[dest]
      if (from && to) {
        list.push({
          key: rKey,
          origin: orig,
          dest,
          change_pct: (detail.relative - 1) * 100,
          relative: detail.relative,
          base_fare: detail.base_period_fare,
          current_fare: detail.as_of_period_fare,
          weight: detail.weight,
          from,
          to,
        })
      }
    })
    return list
  }, [routeFares])

  if (indexQuery.loading || routesQuery.loading) return <LoadingState label="Rendering geospatial corridor map…" />
  if (indexQuery.error) return <ErrorState message={indexQuery.error} />

  const selectedCorridor = activeCorridors.find((c) => c.key === selectedRouteKey) || activeCorridors[0]

  return (
    <div>
      <PageHeader
        title="Geospatial Flight Corridor Map"
        subtitle="Interactive visual map of major Indian trunk flight corridors and route-level inflation dynamics"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SVG Interactive Map */}
        <Card className="lg:col-span-2 flex flex-col items-center bg-slate-900 text-white rounded-xl shadow-lg border-slate-800">
          <div className="w-full flex justify-between items-center px-2 py-1 text-xs text-slate-400 border-b border-slate-800 mb-2">
            <span>India Domestic Air Corridors</span>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span> Fare Rise ({'>'}0%)</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block"></span> Fare Drop ({'<'}0%)</span>
            </div>
          </div>

          <svg viewBox="100 80 620 620" className="w-full max-h-[520px] select-none">
            <defs>
              {/* Radial gradient for airports */}
              <radialGradient id="hubGradient">
                <stop offset="0%" stopColor="#60a5fa" stopOpacity="1" />
                <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.8" />
              </radialGradient>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Approximate India Coastline & Border Vector Path */}
            <path
              d="M 330 110 L 360 130 L 390 170 L 440 200 L 520 220 L 570 250 L 660 210 L 710 230 L 690 280 L 600 300 L 550 340 L 480 400 L 430 460 L 390 530 L 360 620 L 330 670 L 300 700 L 270 660 L 230 520 L 200 420 L 180 340 L 200 270 L 270 200 L 300 130 Z"
              fill="#1e293b"
              stroke="#334155"
              strokeWidth="2"
              strokeDasharray="4 2"
              opacity="0.6"
            />

            {/* Flight Corridor Arcs */}
            {activeCorridors.map((c) => {
              const isSelected = selectedRouteKey === c.key
              const strokeColor = c.change_pct >= 0 ? '#ef4444' : '#10b981'
              const midX = (c.from.x + c.to.x) / 2
              const midY = (c.from.y + c.to.y) / 2 - 30 // Arc curvature

              return (
                <g key={c.key} className="cursor-pointer" onClick={() => setSelectedRouteKey(c.key)}>
                  <path
                    d={`M ${c.from.x} ${c.from.y} Q ${midX} ${midY} ${c.to.x} ${c.to.y}`}
                    fill="none"
                    stroke={isSelected ? '#38bdf8' : strokeColor}
                    strokeWidth={isSelected ? 3.5 : Math.max(1.5, c.weight * 30)}
                    strokeOpacity={isSelected ? 1 : 0.65}
                    className="hover:stroke-cyan-400 transition"
                  />
                  {isSelected && (
                    <circle cx={midX} cy={midY} r="4" fill="#38bdf8" filter="url(#glow)">
                      <animate attributeName="r" values="3;6;3" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}
                </g>
              )
            })}

            {/* Airport Nodes */}
            {Object.values(AIRPORTS).map((apt) => {
              const isAirportSelected = selectedAirport === apt.code
              return (
                <g
                  key={apt.code}
                  transform={`translate(${apt.x}, ${apt.y})`}
                  className="cursor-pointer"
                  onClick={() => setSelectedAirport(apt.code)}
                >
                  <circle r="9" fill="url(#hubGradient)" stroke="#ffffff" strokeWidth="1.5" />
                  <circle r="4" fill="#ffffff" />
                  <text
                    x="12"
                    y="4"
                    fill="#f8fafc"
                    fontSize="11"
                    fontWeight="bold"
                    className="drop-shadow-md"
                  >
                    {apt.code}
                  </text>
                </g>
              )
            })}
          </svg>
          <div className="text-[11px] text-slate-400 pb-2">
            Click on any flight corridor arc or airport hub node to inspect real-time metrics.
          </div>
        </Card>

        {/* Selected Route Detail HUD */}
        <div className="space-y-4">
          <Card title="Corridor Metrics & Inspection">
            {selectedCorridor ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="text-xl font-bold text-slate-900">{selectedCorridor.key}</h3>
                    <p className="text-xs text-muted">
                      {AIRPORTS[selectedCorridor.origin]?.name} ➔ {AIRPORTS[selectedCorridor.dest]?.name}
                    </p>
                  </div>
                  <span
                    className={`text-sm font-bold px-2.5 py-1 rounded ${
                      selectedCorridor.change_pct >= 0 ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {selectedCorridor.change_pct >= 0 ? '+' : ''}
                    {selectedCorridor.change_pct.toFixed(2)}%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-slate-50 p-2.5 rounded">
                    <span className="text-muted block">Current Period Fare</span>
                    <strong className="text-sm font-semibold text-slate-900">₹{selectedCorridor.current_fare.toLocaleString()}</strong>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded">
                    <span className="text-muted block">Base Period Fare</span>
                    <strong className="text-sm font-semibold text-slate-900">₹{selectedCorridor.base_fare.toLocaleString()}</strong>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded">
                    <span className="text-muted block">Price Relative</span>
                    <strong className="text-sm font-semibold text-blue-700">{selectedCorridor.relative.toFixed(3)}</strong>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded">
                    <span className="text-muted block">Basket Weight</span>
                    <strong className="text-sm font-semibold text-slate-900">{(selectedCorridor.weight * 100).toFixed(2)}%</strong>
                  </div>
                </div>

                <div className="pt-2">
                  <span className="text-xs font-semibold text-slate-700 block mb-2">Switch Active Corridor:</span>
                  <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto">
                    {activeCorridors.map((c) => (
                      <button
                        key={c.key}
                        onClick={() => setSelectedRouteKey(c.key)}
                        className={`text-xs px-2 py-1 rounded transition ${
                          selectedRouteKey === c.key
                            ? 'bg-blue-600 text-white font-semibold'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {c.key}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted">Select a flight corridor on the map.</p>
            )}
          </Card>

          <Card title="DGCA Domestic Hub Hubs">
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-800">Delhi (DEL)</span>
                <span className="text-muted">Northern Primary Hub</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-800">Mumbai (BOM)</span>
                <span className="text-muted">Western Primary Hub</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="font-semibold text-slate-800">Bengaluru (BLR)</span>
                <span className="text-muted">Southern Tech Corridor</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="font-semibold text-slate-800">Kolkata (CCU)</span>
                <span className="text-muted">Eastern & NE Gateway</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
