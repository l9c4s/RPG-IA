import React, { useState, useEffect, useRef, useCallback, type DragEvent, type ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen, Upload, CheckCircle, XCircle, RefreshCw,
  ChevronLeft, AlertTriangle, Database, FileText, Sword, Clock, Trash2
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Spinner } from './ui/Spinner'
import { SkeletonTable } from './ui/Skeleton'
import type { KnowledgeStats, PDFSource, PDFSourceType, ProcessingStatus } from '../types'
import { RPG_SYSTEMS } from '../lib/constants'

const EXTRA_RPG_SYSTEMS = [
  ...RPG_SYSTEMS,
  'Cyberpunk RED',
  'GURPS',
  'Fate Core',
  'Blades in the Dark',
  'Generic / Other',
] as const

const SOURCE_TYPES: { value: PDFSourceType; label: string }[] = [
  { value: 'rulebook',   label: 'Core Rulebook' },
  { value: 'sourcebook', label: 'Sourcebook / Setting' },
  { value: 'adventure',  label: 'Adventure Module' },
  { value: 'supplement', label: 'Supplement' },
  { value: 'homebrew',   label: 'Homebrew' },
]

const STATUS_BADGE_VARIANT: Record<ProcessingStatus, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending:    'default',
  processing: 'warning',
  done:       'success',
  error:      'danger',
}

const STATUS_LABELS: Record<ProcessingStatus, string> = {
  pending:    'Pending',
  processing: 'Processing…',
  done:       'Ready',
  error:      'Error',
}

function StatusIcon({ status }: { status: ProcessingStatus }): React.ReactElement {
  if (status === 'pending')    return <Clock      className="w-4 h-4 text-slate-500" />
  if (status === 'processing') return <Spinner    size="sm" />
  if (status === 'done')       return <CheckCircle className="w-4 h-4 text-green-500" />
  return <XCircle className="w-4 h-4 text-red-500" />
}

// ── Stats Panel ────────────────────────────────────────────────────────────
interface StatsPanelProps { stats: KnowledgeStats | null; isLoading: boolean }

function StatsPanel({ stats, isLoading }: StatsPanelProps): React.ReactElement {
  return (
    <div className="card-rune p-6">
      <div className="flex items-center gap-2 mb-4">
        <Database className="w-5 h-5 text-amber-500" />
        <h2 className="font-serif text-amber-400 text-lg tracking-wide">Knowledge Status</h2>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <Spinner size="sm" />
          Loading stats…
        </div>
      ) : stats ? (
        <div className="space-y-4">
          {/* GM Ready indicator */}
          <div className={`flex items-center gap-3 p-3 rounded-lg border ${
            stats.gm_is_ready
              ? 'bg-green-900/30 border-green-700/50'
              : 'bg-red-900/30 border-red-700/50'
          }`}>
            <div className={`w-3 h-3 rounded-full ${
              stats.gm_is_ready ? 'bg-green-500' : 'bg-red-500'
            } ${stats.gm_is_ready ? 'shadow-lg shadow-green-500/50' : 'shadow-lg shadow-red-500/50'} animate-pulse-slow`} />
            <div>
              <p className={`text-sm font-semibold ${stats.gm_is_ready ? 'text-green-300' : 'text-red-300'}`}>
                {stats.gm_is_ready ? 'GM is Ready' : 'GM Needs More Knowledge'}
              </p>
              <p className="text-xs text-slate-500">
                {stats.gm_is_ready
                  ? 'The AI Dungeon Master has enough lore to run your game.'
                  : 'Upload at least one rulebook to unlock the AI Game Master.'}
              </p>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700/50">
              <p className="text-2xl font-serif text-amber-400">{stats.total_chunks.toLocaleString()}</p>
              <p className="text-xs text-slate-500 mt-0.5">Knowledge Chunks</p>
            </div>
            <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700/50">
              <p className="text-2xl font-serif text-amber-400">{stats.total_sources}</p>
              <p className="text-xs text-slate-500 mt-0.5">Source Books</p>
            </div>
            <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700/50">
              <p className="text-2xl font-serif text-amber-400">{stats.systems_covered.length}</p>
              <p className="text-xs text-slate-500 mt-0.5">Systems</p>
            </div>
          </div>

          {/* Systems covered */}
          {stats.systems_covered.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-widest mb-2 font-serif">Systems Covered</p>
              <div className="flex flex-wrap gap-1.5">
                {stats.systems_covered.map((sys) => (
                  <Badge key={sys} variant="info">{sys}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Processing notice */}
          {stats.processing_count > 0 && (
            <div className="flex items-center gap-2 text-amber-400 text-xs bg-amber-900/20 border border-amber-700/30 rounded-md px-3 py-2">
              <Spinner size="sm" />
              {stats.processing_count} book{stats.processing_count > 1 ? 's' : ''} being processed…
            </div>
          )}
        </div>
      ) : (
        <p className="text-slate-500 text-sm font-serif italic">No knowledge data available yet.</p>
      )}
    </div>
  )
}

// ── Upload Form ────────────────────────────────────────────────────────────
interface UploadFormProps { onSuccess: () => void }

function UploadForm({ onSuccess }: UploadFormProps): React.ReactElement {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file,        setFile]        = useState<File | null>(null)
  const [title,       setTitle]       = useState('')
  const [rpgSystem,   setRpgSystem]   = useState('D&D 5e')
  const [sourceType,  setSourceType]  = useState<PDFSourceType>('rulebook')
  const [isDragging,  setIsDragging]  = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error,       setError]       = useState<string | null>(null)
  const [progress,    setProgress]    = useState(0)

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && dropped.type === 'application/pdf') {
      setFile(dropped)
      if (!title) setTitle(dropped.name.replace(/\.pdf$/i, ''))
    } else {
      setError('Only PDF files are accepted.')
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>): void {
    const picked = e.target.files?.[0]
    if (picked) {
      setFile(picked)
      if (!title) setTitle(picked.name.replace(/\.pdf$/i, ''))
    }
  }

  async function handleUpload(): Promise<void> {
    if (!file) { setError('Please select a PDF file.'); return }
    if (!title.trim()) { setError('Please enter a title.'); return }

    setIsUploading(true)
    setError(null)
    setProgress(10)

    try {
      const formData = new FormData()
      formData.append('file',        file)
      formData.append('title',       title.trim())
      formData.append('rpg_system',  rpgSystem)
      formData.append('source_type', sourceType)

      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 8, 85))
      }, 400)

      await api.upload('/books/upload', formData)

      clearInterval(progressInterval)
      setProgress(100)

      setTimeout(() => {
        setFile(null)
        setTitle('')
        setRpgSystem('D&D 5e')
        setSourceType('rulebook')
        setProgress(0)
        setIsUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
        onSuccess()
      }, 800)
    } catch {
      setError('Upload failed. Please check the file and try again.')
      setProgress(0)
      setIsUploading(false)
    }
  }

  return (
    <div className="card-rune p-6">
      <div className="flex items-center gap-2 mb-5">
        <Upload className="w-5 h-5 text-amber-500" />
        <h2 className="font-serif text-amber-400 text-lg tracking-wide">Upload a PDF</h2>
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 mb-4 text-red-300 text-sm">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all duration-200 mb-5 ${
          isDragging
            ? 'border-amber-500 bg-amber-900/20'
            : file
            ? 'border-green-600/60 bg-green-900/10'
            : 'border-slate-600 hover:border-amber-700/60 bg-slate-900/50'
        } ${isUploading ? 'pointer-events-none opacity-70' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
        />

        {file ? (
          <div className="flex flex-col items-center gap-2">
            <CheckCircle className="w-8 h-8 text-green-500" />
            <p className="text-green-300 font-semibold text-sm">{file.name}</p>
            <p className="text-slate-500 text-xs">
              {(file.size / 1024 / 1024).toFixed(2)} MB — Click to change
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <FileText className="w-8 h-8 text-slate-600" />
            <p className="text-slate-300 text-sm font-serif">
              Drop a PDF here or <span className="text-amber-400 underline">browse</span>
            </p>
            <p className="text-slate-600 text-xs">Rulebooks, sourcebooks, adventure modules…</p>
          </div>
        )}
      </div>

      {/* Upload progress */}
      {isUploading && (
        <div className="mb-5 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Spinner size="sm" />
              {progress < 100 ? 'Uploading and processing…' : 'Complete!'}
            </span>
            <span>{progress}%</span>
          </div>
          <div className="hp-track">
            <div
              className="h-full bg-amber-600 transition-all duration-300 rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Form fields */}
      <div className="space-y-4">
        <div>
          <label className="label-rune">Book Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Player's Handbook"
            className="input-dark"
            disabled={isUploading}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-rune">RPG System</label>
            <select
              value={rpgSystem}
              onChange={(e) => setRpgSystem(e.target.value)}
              className="input-dark"
              disabled={isUploading}
            >
              {EXTRA_RPG_SYSTEMS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label-rune">Source Type</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as PDFSourceType)}
              className="input-dark"
              disabled={isUploading}
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>

        <Button
          variant="primary"
          isLoading={isUploading}
          leftIcon={<Upload className="w-4 h-4" />}
          disabled={!file}
          onClick={handleUpload}
          className="w-full justify-center"
        >
          {isUploading ? 'Processing…' : 'Upload to Knowledge Bank'}
        </Button>
      </div>
    </div>
  )
}

// ── Source List ────────────────────────────────────────────────────────────
interface SourceListProps {
  sources:   PDFSource[]
  isLoading: boolean
  onDelete:  (id: number) => void
}

function SourceList({ sources, isLoading, onDelete }: SourceListProps): React.ReactElement {
  if (isLoading) {
    return <SkeletonTable rows={4} />
  }

  if (sources.length === 0) {
    return (
      <div className="text-center py-10">
        <BookOpen className="w-10 h-10 text-slate-700 mx-auto mb-3" />
        <p className="text-slate-500 font-serif italic text-sm">
          No books in the knowledge bank yet.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {sources.map((source) => (
        <div
          key={source.id}
          className={`flex items-center gap-3 p-3 bg-slate-900/50 rounded-lg border transition-colors ${
            source.status === 'error'
              ? 'border-red-700/40'
              : source.status === 'done'
              ? 'border-green-700/20'
              : 'border-slate-700/40'
          }`}
        >
          <div className="shrink-0">
            <StatusIcon status={source.status} />
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-slate-200 text-sm font-semibold truncate">{source.title}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-slate-500 text-xs">{source.rpg_system}</span>
              <span className="text-slate-700 text-xs">·</span>
              <span className="text-slate-500 text-xs capitalize">{source.source_type}</span>
              {source.status === 'done' && (
                <>
                  <span className="text-slate-700 text-xs">·</span>
                  <span className="text-green-600 text-xs">{source.chunk_count.toLocaleString()} chunks</span>
                </>
              )}
            </div>
            {source.status === 'error' && source.error_msg && (
              <p className="text-red-400 text-xs mt-0.5 truncate">{source.error_msg}</p>
            )}
          </div>

          <Badge variant={STATUS_BADGE_VARIANT[source.status]} className="shrink-0 text-xs">
            {STATUS_LABELS[source.status]}
          </Badge>

          <button
            onClick={() => onDelete(source.id)}
            className="shrink-0 p-1 text-slate-600 hover:text-red-400 transition-colors"
            title="Remove"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function KnowledgeGate(): React.ReactElement {
  const { user }                                    = useAuth()
  const [stats,          setStats]                 = useState<KnowledgeStats | null>(null)
  const [sources,        setSources]               = useState<PDFSource[]>([])
  const [statsLoading,   setStatsLoading]          = useState(true)
  const [sourcesLoading, setSourcesLoading]        = useState(true)

  const fetchAll = useCallback(async () => {
    setStatsLoading(true)
    setSourcesLoading(true)
    try {
      const [statsData, sourcesData] = await Promise.all([
        api.get<KnowledgeStats>('/books/stats'),
        api.get<PDFSource[]>('/books'),
      ])
      setStats(statsData)
      setSources(sourcesData)
    } catch {
      // Errors handled per panel
    } finally {
      setStatsLoading(false)
      setSourcesLoading(false)
    }
  }, [])

  useEffect(() => { void fetchAll() }, [fetchAll])

  // Poll while any source is processing
  useEffect(() => {
    const hasProcessing = sources.some(
      (s) => s.status === 'processing' || s.status === 'pending',
    )
    if (!hasProcessing) return

    const interval = setInterval(fetchAll, 5000)
    return () => clearInterval(interval)
  }, [sources, fetchAll])

  async function handleDelete(id: number): Promise<void> {
    try {
      await api.delete(`/books/${id}`)
      setSources((prev) => prev.filter((s) => s.id !== id))
      void fetchAll()
    } catch {
      // Silently fail
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 bg-dungeon-texture">
      {/* Nav */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-amber-700/30 px-4 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/dashboard" className="btn-ghost py-1.5 px-2.5 text-xs">
              <ChevronLeft className="w-3.5 h-3.5" />
              Dashboard
            </Link>
            <span className="text-slate-700">|</span>
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-amber-500" />
              <span className="font-serif text-amber-400">Knowledge Bank</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500 text-xs hidden sm:block">{user?.username}</span>
            <button
              onClick={fetchAll}
              className="p-1.5 text-slate-500 hover:text-amber-400 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-serif text-amber-400 text-shadow-amber">Knowledge Bank</h1>
          <p className="text-slate-400 text-sm mt-1 font-serif italic">
            Feed the AI Dungeon Master with RPG source books and rulebooks
          </p>
        </div>

        {/* Gate blocked banner */}
        {stats && !stats.gm_is_ready && (
          <div className="flex items-start gap-3 bg-red-900/30 border border-red-700/50 rounded-lg px-5 py-4 mb-6 animate-fade-in">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-red-300 font-semibold text-sm">Knowledge Gate is Locked</p>
              <p className="text-red-400/80 text-xs mt-0.5">
                The AI Game Master needs at least one processed rulebook before it can run a session.
                Upload a PDF below to unlock it.
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: stats + source list */}
          <div className="space-y-6">
            <StatsPanel stats={stats} isLoading={statsLoading} />

            <div className="card-rune p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Sword className="w-4 h-4 text-amber-500" />
                  <h2 className="font-serif text-amber-400 text-lg tracking-wide">Library</h2>
                </div>
                <span className="text-xs text-slate-500">
                  {sources.length} book{sources.length !== 1 ? 's' : ''}
                </span>
              </div>
              <SourceList
                sources={sources}
                isLoading={sourcesLoading}
                onDelete={handleDelete}
              />
            </div>
          </div>

          {/* Right: upload form */}
          <div>
            <UploadForm onSuccess={fetchAll} />
          </div>
        </div>
      </main>
    </div>
  )
}
