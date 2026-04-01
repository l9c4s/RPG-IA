import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Map, Loader2, RefreshCw, Compass } from 'lucide-react'
import { api } from '../api/client'
import type { Location } from '../types'

// ─── Icon per location type ────────────────────────────────────────────────
const TYPE_COLOR: Record<Location['type'], string> = {
  city:        '#f59e0b',   // amber
  dungeon:     '#ef4444',   // red
  wilderness:  '#22c55e',   // green
  landmark:    '#a78bfa',   // violet
  unknown:     '#64748b',   // slate
}

const TYPE_LABEL: Record<Location['type'], string> = {
  city:        '🏰',
  dungeon:     '🗡️',
  wilderness:  '🌲',
  landmark:    '✦',
  unknown:     '?',
}

// ─── Tooltip ───────────────────────────────────────────────────────────────
interface TooltipProps {
  location: Location
  svgWidth: number
  svgHeight: number
}

function LocationTooltip({ location, svgWidth, svgHeight }: TooltipProps): React.ReactElement {
  const x = (location.x / 100) * svgWidth
  const y = (location.y / 100) * svgHeight

  // Flip to left if too close to right edge, up if too close to bottom
  const flipX = x > svgWidth * 0.6
  const flipY = y > svgHeight * 0.7

  return (
    <foreignObject
      x={flipX ? x - 160 : x + 12}
      y={flipY ? y - 80 : y + 12}
      width="150"
      height="80"
      style={{ overflow: 'visible' }}
    >
      <div className="bg-slate-900/95 border border-amber-700/60 rounded-md px-2.5 py-2 shadow-amber text-xs pointer-events-none">
        <p className="font-serif text-amber-400 font-semibold leading-tight truncate">{location.name}</p>
        <p className="text-slate-400 mt-0.5 leading-snug line-clamp-2">{location.description}</p>
        {location.is_current && (
          <p className="text-green-400 mt-1 flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full" />
            Current location
          </p>
        )}
        {!location.discovered && (
          <p className="text-slate-600 mt-1 italic">Undiscovered</p>
        )}
      </div>
    </foreignObject>
  )
}

// ─── Props ─────────────────────────────────────────────────────────────────
interface WorldMapProps {
  campaignId:       string
  onLocationSelect: (locationName: string) => void
}

// ─── Main Component ────────────────────────────────────────────────────────
export default function WorldMap({ campaignId, onLocationSelect }: WorldMapProps): React.ReactElement {
  const svgRef              = useRef<SVGSVGElement>(null)
  const [locations,    setLocations]    = useState<Location[]>([])
  const [isLoading,    setIsLoading]    = useState(true)
  const [hoveredId,    setHoveredId]    = useState<string | null>(null)
  const [svgSize,      setSvgSize]      = useState({ width: 300, height: 400 })

  const fetchLocations = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await api.get<Location[]>(`/campaigns/${campaignId}/locations`)
      setLocations(data)
    } catch {
      // Use placeholder locations if API not ready
      setLocations(PLACEHOLDER_LOCATIONS)
    } finally {
      setIsLoading(false)
    }
  }, [campaignId])

  useEffect(() => { void fetchLocations() }, [fetchLocations])

  // Track SVG size for tooltip positioning
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const obs = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setSvgSize({ width: entry.contentRect.width, height: entry.contentRect.height })
      }
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const hoveredLocation = locations.find((l) => l.id === hoveredId) ?? null

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-amber-700/20 shrink-0">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-amber-500" />
          <span className="font-serif text-amber-400 text-sm">World Map</span>
        </div>
        <button
          onClick={fetchLocations}
          className="p-1 text-slate-600 hover:text-amber-400 transition-colors"
          title="Refresh map"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Map canvas */}
      <div className="flex-1 relative overflow-hidden p-2">
        {isLoading ? (
          <div className="flex items-center justify-center h-full gap-2 text-slate-400 text-xs">
            <Loader2 className="w-4 h-4 animate-spin" />
            Charting the realm…
          </div>
        ) : (
          <svg
            ref={svgRef}
            viewBox="0 0 100 130"
            className="w-full h-full"
            style={{ fontFamily: 'Cinzel, Georgia, serif' }}
          >
            {/* Parchment background */}
            <defs>
              <radialGradient id="bg-gradient" cx="50%" cy="50%" r="60%">
                <stop offset="0%"   stopColor="#1e293b" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#0f172a" stopOpacity="1" />
              </radialGradient>

              {/* Subtle grid */}
              <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#334155" strokeWidth="0.15" opacity="0.4" />
              </pattern>

              {/* Glow filter */}
              <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="1.5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>

              {/* Current location pulse */}
              <filter id="pulse" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="2" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Background */}
            <rect width="100" height="130" fill="url(#bg-gradient)" />
            <rect width="100" height="130" fill="url(#grid)" />

            {/* Map border */}
            <rect
              x="1" y="1" width="98" height="128"
              fill="none"
              stroke="#78350f"
              strokeWidth="0.5"
              strokeDasharray="2,1"
              opacity="0.5"
            />

            {/* Inner border */}
            <rect
              x="2.5" y="2.5" width="95" height="125"
              fill="none"
              stroke="#78350f"
              strokeWidth="0.25"
              opacity="0.3"
            />

            {/* Title */}
            <text
              x="50" y="8"
              textAnchor="middle"
              fill="#d97706"
              fontSize="3.5"
              fontFamily="Cinzel, serif"
              opacity="0.7"
            >
              Known World
            </text>
            <line x1="10" y1="9.5" x2="90" y2="9.5" stroke="#78350f" strokeWidth="0.25" opacity="0.4" />

            {/* Travel paths between discovered locations */}
            {locations
              .filter((l) => l.discovered)
              .flatMap((from, i, arr) =>
                arr.slice(i + 1).map((to) => (
                  <line
                    key={`path-${from.id}-${to.id}`}
                    x1={from.x}
                    y1={from.y * 1.3}  // scale y to viewBox height
                    x2={to.x}
                    y2={to.y * 1.3}
                    stroke="#78350f"
                    strokeWidth="0.3"
                    strokeDasharray="1.5,1"
                    opacity="0.3"
                  />
                )),
              )}

            {/* Location nodes */}
            {locations.map((loc) => {
              const cx      = loc.x
              const cy      = loc.y * 1.3   // scale 0-100% y → 0-130 viewBox
              const color   = TYPE_COLOR[loc.type]
              const isCurr  = loc.is_current
              const isHover = hoveredId === loc.id
              const size    = isCurr ? 3.5 : isHover ? 3 : 2.5
              const opacity = loc.discovered ? 1 : 0.35

              return (
                <g
                  key={loc.id}
                  transform={`translate(${cx}, ${cy})`}
                  style={{ cursor: loc.discovered ? 'pointer' : 'default' }}
                  opacity={opacity}
                  onClick={() => loc.discovered && onLocationSelect(loc.name)}
                  onMouseEnter={() => setHoveredId(loc.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  {/* Current location pulse ring */}
                  {isCurr && (
                    <circle
                      r={size + 2}
                      fill="none"
                      stroke={color}
                      strokeWidth="0.4"
                      opacity="0.4"
                      filter="url(#pulse)"
                    />
                  )}

                  {/* Node circle */}
                  <circle
                    r={size}
                    fill={isCurr ? color : `${color}33`}
                    stroke={color}
                    strokeWidth={isHover ? 0.6 : 0.4}
                    filter={isCurr || isHover ? 'url(#glow)' : undefined}
                  />

                  {/* Type emoji / symbol */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={size * 0.9}
                    fill={color}
                  >
                    {TYPE_LABEL[loc.type]}
                  </text>

                  {/* Location name */}
                  <text
                    y={size + 2.5}
                    textAnchor="middle"
                    fontSize="2"
                    fill={isCurr ? '#fbbf24' : '#94a3b8'}
                    fontFamily="Cinzel, serif"
                    fontWeight={isCurr ? '600' : '400'}
                  >
                    {loc.name.length > 14 ? loc.name.slice(0, 13) + '…' : loc.name}
                  </text>
                </g>
              )
            })}

            {/* Hover tooltip */}
            {hoveredLocation && (
              <LocationTooltip
                location={hoveredLocation}
                svgWidth={svgSize.width}
                svgHeight={svgSize.height}
              />
            )}
          </svg>
        )}
      </div>

      {/* Legend */}
      <div className="px-3 py-2 border-t border-amber-700/20 shrink-0">
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {(Object.entries(TYPE_LABEL) as [Location['type'], string][]).map(([type, icon]) => (
            <span key={type} className="flex items-center gap-1 text-xs text-slate-500">
              <span style={{ color: TYPE_COLOR[type] }}>{icon}</span>
              <span className="capitalize">{type}</span>
            </span>
          ))}
        </div>
        <p className="text-slate-700 text-xs mt-1 italic font-serif">
          Click a location to travel there
        </p>
      </div>
    </div>
  )
}

// ─── Placeholder data (shown when API is not yet available) ────────────────
const PLACEHOLDER_LOCATIONS: Location[] = [
  {
    id: '1', name: 'Phandalin', description: 'A small frontier town. The party's base of operations.',
    x: 42, y: 45, type: 'city', is_current: true, discovered: true,
  },
  {
    id: '2', name: 'Tresendar Manor', description: 'Ruins of an old manor, now occupied by the Redbrands.',
    x: 48, y: 52, type: 'dungeon', is_current: false, discovered: true,
  },
  {
    id: '3', name: 'Cragmaw Hideout', description: 'A goblin lair hidden in the forest.',
    x: 28, y: 30, type: 'dungeon', is_current: false, discovered: true,
  },
  {
    id: '4', name: 'Wave Echo Cave', description: 'The legendary mine from the Phandelver Pact.',
    x: 62, y: 38, type: 'dungeon', is_current: false, discovered: false,
  },
  {
    id: '5', name: 'Neverwinter Road', description: 'The main road leading north to the city.',
    x: 30, y: 18, type: 'landmark', is_current: false, discovered: true,
  },
  {
    id: '6', name: 'Triboar Trail', description: 'A secondary road heading east.',
    x: 65, y: 20, type: 'wilderness', is_current: false, discovered: true,
  },
  {
    id: '7', name: '???', description: 'An unknown region to the south.',
    x: 50, y: 72, type: 'unknown', is_current: false, discovered: false,
  },
]
