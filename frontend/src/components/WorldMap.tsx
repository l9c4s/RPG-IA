import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Loader2, RefreshCw, Compass, Map } from 'lucide-react'
import { api } from '../api/client'
import type { Location } from '../types'

// ─── Config ────────────────────────────────────────────────────────────────
const TYPE_COLOR: Record<Location['type'], string> = {
  city:       '#f59e0b',
  dungeon:    '#ef4444',
  wilderness: '#22c55e',
  landmark:   '#a78bfa',
  unknown:    '#64748b',
}

const TYPE_LABEL: Record<Location['type'], string> = {
  city:       '🏰',
  dungeon:    '⚔️',
  wilderness: '🌲',
  landmark:   '✦',
  unknown:    '?',
}

// Pin SVG path: ponta na origem (0,0), corpo circular acima
// r = raio do círculo, stem = distância da ponta ao fundo do círculo
function pinPath(r: number, stem: number): string {
  const cy = -(r + stem)
  return [
    `M 0,0`,
    `C -${(r * 0.45).toFixed(1)},${(cy * 0.35).toFixed(1)} -${r},${(cy * 0.65).toFixed(1)} -${r},${cy}`,
    `A ${r},${r} 0 0 1 ${r},${cy}`,
    `C ${r},${(cy * 0.65).toFixed(1)} ${(r * 0.45).toFixed(1)},${(cy * 0.35).toFixed(1)} 0,0`,
    'Z',
  ].join(' ')
}

// ─── Types ─────────────────────────────────────────────────────────────────
interface MapImage {
  image_id:  string
  image_url: string | null
  status:    string
}

interface TooltipProps {
  location: Location
  svgW:     number
  svgH:     number
}

// ─── Tooltip ───────────────────────────────────────────────────────────────
function LocationTooltip({ location, svgW, svgH }: TooltipProps): React.ReactElement {
  const cx = (location.x / 100) * svgW
  const cy = (location.y / 100) * svgH
  const flipX = cx > svgW * 0.6
  const flipY = cy > svgH * 0.7

  return (
    <foreignObject
      x={flipX ? cx - 164 : cx + 14}
      y={flipY ? cy - 84 : cy + 14}
      width="150"
      height="80"
      style={{ overflow: 'visible', pointerEvents: 'none' }}
    >
      <div className="bg-slate-900/95 border border-amber-700/60 rounded-md px-2.5 py-2 shadow-lg text-xs" style={{ pointerEvents: 'none' }}>
        <p className="font-serif text-amber-400 font-semibold leading-tight truncate">{location.name}</p>
        <p className="text-slate-400 mt-0.5 leading-snug line-clamp-2">{location.description}</p>
        {location.is_current && (
          <p className="text-green-400 mt-1 flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full" />
            Localização atual
          </p>
        )}
        {!location.discovered && (
          <p className="text-slate-600 mt-1 italic">Não descoberto</p>
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
  const wrapRef = useRef<HTMLDivElement>(null)

  const [mapImage,    setMapImage]    = useState<MapImage | null>(null)
  const [mapPngUrl,   setMapPngUrl]   = useState<string | null>(null)
  const [locations,   setLocations]   = useState<Location[]>([])
  const [isLoading,   setIsLoading]   = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedId,  setSelectedId]  = useState<string | null>(null)
  const [wrapSize,    setWrapSize]    = useState({ w: 800, h: 500 })

  // Track container size for tooltip positioning
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const obs = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (r) setWrapSize({ w: r.width, h: r.height })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    const [imgResult, locResult] = await Promise.allSettled([
      api.get<MapImage>(`/images/map/campaign/${campaignId}`),
      api.get<Location[]>(`/campaigns/${campaignId}/locations`),
    ])

    setMapImage(imgResult.status === 'fulfilled' ? imgResult.value : null)
    setLocations(locResult.status === 'fulfilled' ? locResult.value : PLACEHOLDER_LOCATIONS)
    setIsLoading(false)
  }, [campaignId])

  useEffect(() => { void fetchAll() }, [fetchAll])

  // Quando o mapa é um SVG, extrai a URL do PNG embutido
  // (browsers bloqueiam recursos externos em SVG carregado via <img>)
  useEffect(() => {
    const url = mapImage?.image_url
    if (!url) { setMapPngUrl(null); return }
    if (!url.endsWith('.svg')) { setMapPngUrl(url); return }

    let cancelled = false
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        if (cancelled) return
        const doc = new DOMParser().parseFromString(text, 'image/svg+xml')
        const href =
          doc.querySelector('image')?.getAttribute('href') ??
          doc.querySelector('image')?.getAttributeNS('http://www.w3.org/1999/xlink', 'href') ??
          null
        setMapPngUrl(href)
      })
      .catch(() => { if (!cancelled) setMapPngUrl(null) })

    return () => { cancelled = true }
  }, [mapImage?.image_url])

  const generateMap = useCallback(async () => {
    if (isGenerating || locations.length === 0) return
    setIsGenerating(true)
    try {
      const res = await api.post<{ image_id: string; status: string }>(
        '/generate/map',
        {
          description: 'A detailed fantasy world map with diverse biomes, mountains, forests, rivers, coastal regions, and scattered settlements.',
          campaign_id: campaignId,
          locations: locations.map((l) => ({
            id:          l.id,
            name:        l.name,
            type:        l.type,
            x:           l.x,
            y:           l.y,
            is_current:  l.is_current,
            discovered:  l.discovered,
          })),
        },
      )

      // SSE — aguarda geração completar
      const evtSource = new EventSource(`/api/images/${res.image_id}/stream`)
      evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data as string) as { status: string; image_url?: string }
        if (data.status === 'completed') {
          evtSource.close()
          setMapImage({ image_id: res.image_id, image_url: data.image_url ?? null, status: 'completed' })
          setIsGenerating(false)
        } else if (data.status === 'failed') {
          evtSource.close()
          setIsGenerating(false)
        }
      }
      evtSource.onerror = () => { evtSource.close(); setIsGenerating(false) }
    } catch {
      setIsGenerating(false)
    }
  }, [campaignId, isGenerating, locations])

  const selectedLoc = locations.find((l) => l.id === selectedId) ?? null

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-amber-700/20 shrink-0">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-amber-500" />
          <span className="font-serif text-amber-400 text-sm">World Map</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={generateMap}
            disabled={isGenerating || locations.length === 0}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-xs text-amber-400 border border-amber-700/40 hover:bg-amber-900/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Gerar novo mapa com DALL-E"
          >
            {isGenerating
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <Map className="w-3 h-3" />}
            {isGenerating ? 'Gerando…' : 'Gerar Mapa'}
          </button>
          <button
            onClick={fetchAll}
            className="p-1 text-slate-600 hover:text-amber-400 transition-colors"
            title="Atualizar"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Map canvas */}
      <div ref={wrapRef} className="flex-1 relative overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full gap-2 text-slate-400 text-xs">
            <Loader2 className="w-4 h-4 animate-spin" />
            Charting the realm…
          </div>
        ) : (
          <>
            {/* Background — PNG extraído do SVG ou fallback pergaminho */}
            {mapPngUrl ? (
              <img
                src={mapPngUrl}
                alt="World Map"
                className="absolute inset-0 w-full h-full object-cover"
                draggable={false}
              />
            ) : (
              <svg
                className="absolute inset-0 w-full h-full"
                xmlns="http://www.w3.org/2000/svg"
                preserveAspectRatio="xMidYMid slice"
              >
                <defs>
                  <radialGradient id="bg-grad" cx="50%" cy="50%" r="70%">
                    <stop offset="0%"   stopColor="#1a1f2e" />
                    <stop offset="100%" stopColor="#0a0d14" />
                  </radialGradient>
                  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ffffff" strokeWidth="0.3" opacity="0.06" />
                  </pattern>
                  <pattern id="dots" width="80" height="80" patternUnits="userSpaceOnUse">
                    <circle cx="40" cy="40" r="0.8" fill="#a78bfa" opacity="0.12" />
                    <circle cx="0"  cy="0"  r="0.8" fill="#a78bfa" opacity="0.08" />
                    <circle cx="80" cy="0"  r="0.8" fill="#a78bfa" opacity="0.08" />
                    <circle cx="0"  cy="80" r="0.8" fill="#a78bfa" opacity="0.08" />
                    <circle cx="80" cy="80" r="0.8" fill="#a78bfa" opacity="0.08" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#bg-grad)" />
                <rect width="100%" height="100%" fill="url(#grid)" />
                <rect width="100%" height="100%" fill="url(#dots)" />
                {/* decorative corner runes */}
                <text x="16" y="28" fontSize="18" fill="#a78bfa" opacity="0.12" fontFamily="serif">✦</text>
                {/* subtle vignette */}
                <radialGradient id="vignette" cx="50%" cy="50%" r="70%">
                  <stop offset="60%"  stopColor="transparent" />
                  <stop offset="100%" stopColor="#000000" stopOpacity="0.55" />
                </radialGradient>
                <rect width="100%" height="100%" fill="url(#vignette)" />
                {/* "no map" hint — unobtrusive */}
                <text
                  x="50%" y="92%" textAnchor="middle"
                  fontSize="10" fill="#334155" fontFamily="Cinzel, serif" letterSpacing="1"
                >
                  Mapa não gerado — peça ao GM para descrever o mundo
                </text>
              </svg>
            )}

            {/* SVG overlay — location markers */}
            <svg
              className="absolute inset-0 w-full h-full"
              viewBox={`0 0 ${wrapSize.w} ${wrapSize.h}`}
              style={{ fontFamily: 'Cinzel, Georgia, serif' }}
            >
              <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="pulse" x="-100%" y="-100%" width="300%" height="300%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                {/* Dark shadow behind text for readability on map image */}
                <filter id="text-shadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor="#000" floodOpacity="0.9" />
                </filter>
              </defs>

              {/* Location nodes */}
              {locations.map((loc) => {
                const cx         = (loc.x / 100) * wrapSize.w
                const cy         = (loc.y / 100) * wrapSize.h
                const color      = TYPE_COLOR[loc.type]
                const isCurr     = loc.is_current
                const isSelected = selectedId === loc.id
                const r          = isCurr ? 10 : 8
                const stem       = 5
                const pinCY      = -(r + stem)   // centro do círculo do pin
                const opacity    = loc.discovered ? 1 : 0.35
                const label      = loc.name.length > 14 ? loc.name.slice(0, 13) + '…' : loc.name
                const labelY     = pinCY - r - 6  // acima do topo do pin

                return (
                  <g
                    key={loc.id}
                    transform={`translate(${cx}, ${cy})`}
                    opacity={opacity}
                  >
                    {/* Anel pulsante — localização atual */}
                    {isCurr && (
                      <>
                        <circle r={r + 11} fill="none" stroke={color} strokeWidth="1" opacity="0.2" filter="url(#pulse)" style={{ pointerEvents: 'none' }} />
                        <circle r={r + 7}  fill="none" stroke={color} strokeWidth="1.5" opacity="0.4" filter="url(#pulse)" style={{ pointerEvents: 'none' }} />
                      </>
                    )}

                    {/* Sombra do pin */}
                    <path
                      d={pinPath(r, stem)}
                      fill="#000"
                      opacity="0.5"
                      transform="translate(2,3)"
                      style={{ pointerEvents: 'none' }}
                    />

                    {/* Corpo do pin */}
                    <path
                      d={pinPath(r, stem)}
                      fill={isCurr ? color : `${color}cc`}
                      stroke={isSelected ? '#fff' : color}
                      strokeWidth={isSelected ? 2 : 1.5}
                      filter={isCurr || isSelected ? 'url(#glow)' : undefined}
                      style={{ pointerEvents: 'none' }}
                    />

                    {/* Brilho interno no círculo do pin */}
                    <circle
                      cx={0} cy={pinCY}
                      r={r * 0.55}
                      fill="#fff"
                      opacity={isCurr ? 0.25 : 0.15}
                      style={{ pointerEvents: 'none' }}
                    />

                    {/* Ícone do tipo */}
                    <text
                      x={0} y={pinCY}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={r * 1.05}
                      style={{ pointerEvents: 'none' }}
                    >
                      {TYPE_LABEL[loc.type]}
                    </text>

                    {/* Label com fundo */}
                    <rect
                      x={-((label.length * 4.2) / 2 + 4)}
                      y={labelY - 8}
                      width={label.length * 4.2 + 8}
                      height={13}
                      rx={3}
                      fill="#0a0d14"
                      opacity="0.72"
                      style={{ pointerEvents: 'none' }}
                    />
                    <text
                      x={0} y={labelY}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="9"
                      fill={isCurr ? '#fbbf24' : '#e2e8f0'}
                      fontFamily="Cinzel, serif"
                      fontWeight={isCurr ? '700' : '500'}
                      letterSpacing="0.3"
                      style={{ pointerEvents: 'none' }}
                    >
                      {label}
                    </text>

                    {/* Área de hit invisível — somente clique */}
                    <circle
                      r={r + 8}
                      fill="transparent"
                      style={{ cursor: loc.discovered ? 'pointer' : 'default' }}
                      onClick={() => {
                        if (!loc.discovered) return
                        setSelectedId((prev) => prev === loc.id ? null : loc.id)
                        onLocationSelect(loc.name)
                      }}
                    />
                  </g>
                )
              })}

              {/* Click tooltip */}
              {selectedLoc && (
                <LocationTooltip
                  location={selectedLoc}
                  svgW={wrapSize.w}
                  svgH={wrapSize.h}
                />
              )}
            </svg>
          </>
        )}
      </div>

      {/* Selected location info */}
      {selectedLoc && (
        <div className="px-3 py-2.5 border-t border-amber-700/20 shrink-0">
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-sm backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-amber-300 uppercase tracking-widest text-[9px] font-semibold">Selecionado</p>
                <p className="font-serif text-slate-100 font-semibold">{selectedLoc.name}</p>
              </div>
              <span className="text-xs text-slate-500 capitalize">{selectedLoc.type}</span>
            </div>
            <p className="text-slate-400 text-xs mt-1.5 leading-snug">{selectedLoc.description}</p>
            <div className="mt-2.5 flex flex-wrap gap-2 text-xs">
              {selectedLoc.is_current && (
                <span className="px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 border border-green-700/40">
                  Localização atual
                </span>
              )}
              {!selectedLoc.discovered && (
                <span className="px-2 py-0.5 rounded-full bg-red-900/50 text-red-400 border border-red-700/40">
                  Não descoberto
                </span>
              )}
              {selectedLoc.discovered && !selectedLoc.is_current && (
                <button
                  type="button"
                  onClick={() => onLocationSelect(selectedLoc.name)}
                  className="px-3 py-0.5 rounded-full bg-amber-900/50 text-amber-400 border border-amber-700/40 hover:bg-amber-800/60 transition-colors"
                >
                  Viajar para cá
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Placeholder locations ──────────────────────────────────────────────────
const PLACEHOLDER_LOCATIONS: Location[] = [
  {
    id: '1', name: 'Phandalin',
    description: "Pequena cidade fronteiriça — base de operações do grupo.",
    x: 42, y: 45, type: 'city', is_current: true, discovered: true,
  },
  {
    id: '2', name: 'Solar de Tresendar',
    description: 'Ruínas de um antigo solar, ocupado pelos Redbrands.',
    x: 48, y: 52, type: 'dungeon', is_current: false, discovered: true,
  },
  {
    id: '3', name: 'Esconderijo Cragmaw',
    description: 'Covil goblin escondido na floresta.',
    x: 28, y: 30, type: 'dungeon', is_current: false, discovered: true,
  },
  {
    id: '4', name: 'Caverna Wave Echo',
    description: 'A lendária mina do Pacto de Phandelver.',
    x: 62, y: 38, type: 'dungeon', is_current: false, discovered: false,
  },
  {
    id: '5', name: 'Estrada de Neverwinter',
    description: 'Estrada principal ao norte rumo à cidade.',
    x: 30, y: 18, type: 'landmark', is_current: false, discovered: true,
  },
  {
    id: '6', name: 'Trilha Triboar',
    description: 'Estrada secundária rumo ao leste.',
    x: 65, y: 20, type: 'wilderness', is_current: false, discovered: true,
  },
  {
    id: '7', name: '???',
    description: 'Uma região desconhecida ao sul.',
    x: 50, y: 72, type: 'unknown', is_current: false, discovered: false,
  },
]
