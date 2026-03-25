import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Sword, Plus, Book, Map, Users, LogOut,
  ChevronRight, Loader2, AlertCircle, BookOpen, Clock, X
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import type { Campaign, CreateCampaignRequest } from '../api/types'

const RPG_SYSTEMS = [
  'D&D 5e', 'Pathfinder 2e', 'Call of Cthulhu', 'Cyberpunk RED',
  'Vampire: The Masquerade', 'Shadowrun', 'GURPS', 'Fate Core',
  'Blades in the Dark', 'Custom',
]

const STATUS_LABELS: Record<Campaign['status'], string> = {
  active:    'Active',
  paused:    'Paused',
  completed: 'Completed',
  archived:  'Archived',
}

const STATUS_COLORS: Record<Campaign['status'], string> = {
  active:    'badge-success',
  paused:    'badge-warning',
  completed: 'badge-info',
  archived:  'badge-error',
}

// ── Create Campaign Modal ──────────────────────────────────────────────────
interface CreateModalProps {
  onClose:  () => void
  onCreate: (campaign: Campaign) => void
}

function CreateCampaignModal({ onClose, onCreate }: CreateModalProps): React.ReactElement {
  const [title,      setTitle]      = useState('')
  const [description, setDescription] = useState('')
  const [rpgSystem,  setRpgSystem]  = useState('D&D 5e')
  const [isLoading,  setIsLoading]  = useState(false)
  const [error,      setError]      = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    if (!title.trim()) { setError('Campaign title is required.'); return }

    setIsLoading(true)
    setError(null)
    try {
      const payload: CreateCampaignRequest = {
        title:       title.trim(),
        description: description.trim(),
        rpg_system:  rpgSystem,
      }
      const campaign = await api.post<Campaign>('/campaigns', payload)
      onCreate(campaign)
    } catch {
      setError('Failed to create campaign. Try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="card-rune w-full max-w-lg p-8 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-amber-400 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-serif text-amber-400 mb-6 tracking-wide">
          New Campaign
        </h2>

        {error && (
          <div className="flex items-start gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 mb-5 text-red-300 text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label-rune">Campaign Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="The Lost Mines of Phandelver"
              className="input-dark"
              maxLength={120}
              autoFocus
            />
          </div>

          <div>
            <label className="label-rune">RPG System</label>
            <select
              value={rpgSystem}
              onChange={(e) => setRpgSystem(e.target.value)}
              className="input-dark"
            >
              {RPG_SYSTEMS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label-rune">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A party of adventurers ventures into the Sword Coast…"
              className="input-dark resize-none h-24"
              maxLength={500}
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-ghost flex-1 justify-center"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary flex-1 justify-center" disabled={isLoading}>
              {isLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</>
              ) : (
                <><Plus className="w-4 h-4" /> Create Campaign</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Campaign Card ──────────────────────────────────────────────────────────
interface CampaignCardProps { campaign: Campaign }

function CampaignCard({ campaign }: CampaignCardProps): React.ReactElement {
  const navigate = useNavigate()

  const formattedDate = new Date(campaign.updated_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })

  return (
    <div className="card-rune p-5 hover:border-amber-600/60 transition-all duration-200 group">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-amber-400 text-lg truncate group-hover:text-amber-300 transition-colors">
            {campaign.title}
          </h3>
          <p className="text-slate-500 text-xs mt-0.5 font-serif">{campaign.rpg_system}</p>
        </div>
        <span className={STATUS_COLORS[campaign.status] + ' badge shrink-0'}>
          {STATUS_LABELS[campaign.status]}
        </span>
      </div>

      {campaign.description && (
        <p className="text-slate-400 text-sm leading-relaxed line-clamp-2 mb-4 font-serif italic">
          {campaign.description}
        </p>
      )}

      <div className="flex items-center gap-4 text-slate-500 text-xs mb-4">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formattedDate}
        </span>
        {campaign.session_count !== undefined && (
          <span className="flex items-center gap-1">
            <Book className="w-3 h-3" />
            {campaign.session_count} session{campaign.session_count !== 1 ? 's' : ''}
          </span>
        )}
        {campaign.player_count !== undefined && (
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3" />
            {campaign.player_count} player{campaign.player_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => navigate(`/campaign/${campaign.id}`)}
          className="btn-primary flex-1 justify-center text-xs py-1.5"
        >
          <Sword className="w-3.5 h-3.5" />
          Play
        </button>
        <button
          onClick={() => navigate(`/campaign/${campaign.id}/characters`)}
          className="btn-ghost px-3 py-1.5 text-xs"
          title="Characters"
        >
          <Users className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => navigate(`/campaign/${campaign.id}/map`)}
          className="btn-ghost px-3 py-1.5 text-xs"
          title="World Map"
        >
          <Map className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function Dashboard(): React.ReactElement {
  const { user, logout }               = useAuth()
  const [campaigns,  setCampaigns]     = useState<Campaign[]>([])
  const [isLoading,  setIsLoading]     = useState(true)
  const [error,      setError]         = useState<string | null>(null)
  const [showCreate, setShowCreate]    = useState(false)
  const [filterStatus, setFilterStatus] = useState<Campaign['status'] | 'all'>('all')

  const fetchCampaigns = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.get<Campaign[]>('/campaigns')
      setCampaigns(data)
    } catch {
      setError('Failed to load campaigns. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { void fetchCampaigns() }, [fetchCampaigns])

  const filtered = filterStatus === 'all'
    ? campaigns
    : campaigns.filter((c) => c.status === filterStatus)

  return (
    <div className="min-h-screen bg-slate-900 bg-dungeon-texture">
      {/* ── Top nav ── */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-amber-700/30 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-amber-600/20 rounded-full flex items-center justify-center border border-amber-600/40">
              <Sword className="w-4 h-4 text-amber-500" />
            </div>
            <span className="font-serif text-amber-400 text-lg tracking-wide">RPG-IA</span>
          </div>

          <div className="flex items-center gap-3">
            <Link to="/knowledge" className="btn-ghost py-1.5 text-xs">
              <BookOpen className="w-3.5 h-3.5" />
              Knowledge
            </Link>
            <div className="w-px h-5 bg-slate-700" />
            <span className="text-slate-400 text-sm hidden sm:block font-serif">
              {user?.username}
            </span>
            <button onClick={logout} className="btn-ghost py-1.5 px-2.5 text-xs" title="Sign out">
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </nav>

      {/* ── Main content ── */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Header row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-serif text-amber-400 text-shadow-amber">
              Your Campaigns
            </h1>
            <p className="text-slate-400 text-sm mt-1 font-serif italic">
              Choose your adventure, {user?.username}
            </p>
          </div>
          <button onClick={() => setShowCreate(true)} className="btn-primary shrink-0">
            <Plus className="w-4 h-4" />
            New Campaign
          </button>
        </div>

        {/* Filter tabs */}
        {campaigns.length > 0 && (
          <div className="flex gap-2 mb-6 flex-wrap">
            {(['all', 'active', 'paused', 'completed', 'archived'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`px-3 py-1 rounded-full text-xs font-serif transition-all border ${
                  filterStatus === s
                    ? 'bg-amber-600/30 border-amber-600/60 text-amber-300'
                    : 'bg-transparent border-slate-700 text-slate-500 hover:border-amber-700/50 hover:text-slate-300'
                }`}
              >
                {s === 'all' ? 'All' : STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-lg px-5 py-4 mb-6 text-red-300 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button
              onClick={fetchCampaigns}
              className="ml-auto text-xs underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="w-8 h-8 text-amber-600 animate-spin" />
            <p className="text-slate-400 font-serif italic text-sm">
              Unrolling the campaign scrolls…
            </p>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && filtered.length === 0 && (
          <div className="text-center py-20">
            <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6 border border-amber-700/30">
              <Map className="w-10 h-10 text-amber-700/60" />
            </div>
            <h2 className="text-xl font-serif text-slate-300 mb-2">
              {filterStatus === 'all' ? 'No campaigns yet' : `No ${filterStatus} campaigns`}
            </h2>
            <p className="text-slate-500 font-serif italic text-sm mb-6">
              {filterStatus === 'all'
                ? 'The world awaits. Create your first campaign to begin.'
                : 'Try a different filter.'}
            </p>
            {filterStatus === 'all' && (
              <button onClick={() => setShowCreate(true)} className="btn-primary">
                <Plus className="w-4 h-4" />
                Create First Campaign
              </button>
            )}
          </div>
        )}

        {/* Campaign grid */}
        {!isLoading && filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((campaign) => (
              <CampaignCard key={campaign.id} campaign={campaign} />
            ))}
          </div>
        )}

        {/* Quick links */}
        {!isLoading && (
          <div className="mt-10 pt-8 border-t border-amber-700/20">
            <p className="text-slate-500 text-xs uppercase tracking-widest font-serif mb-4">
              Quick Links
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/knowledge" className="btn-ghost text-xs py-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                Knowledge Bank
                <ChevronRight className="w-3 h-3 text-slate-600" />
              </Link>
            </div>
          </div>
        )}
      </main>

      {/* Create modal */}
      {showCreate && (
        <CreateCampaignModal
          onClose={() => setShowCreate(false)}
          onCreate={(campaign) => {
            setCampaigns((prev) => [campaign, ...prev])
            setShowCreate(false)
          }}
        />
      )}
    </div>
  )
}
