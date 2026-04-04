import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Sword, Plus, Book, Map, Users, Trash2,
  ChevronRight, AlertCircle, BookOpen, Clock, Bot,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { campaignApi } from '../api/campaigns'
import { useAuth } from '../hooks/useAuth'
import { AppLayout } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { Modal } from '../components/ui/Modal'
import { Input } from '../components/ui/Input'
import { SkeletonCard } from '../components/ui/Skeleton'
import type { Campaign, CreateCampaignRequest, CampaignStatus } from '../types'
import { RPG_SYSTEMS } from '../lib/constants'
import { formatDate, truncate } from '../lib/utils'

const STATUS_LABELS: Record<CampaignStatus, string> = {
  lobby:     'Lobby',
  active:    'Active',
  paused:    'Paused',
  completed: 'Completed',
  archived:  'Archived',
}

const STATUS_BADGE_VARIANT: Record<CampaignStatus, 'success' | 'warning' | 'info' | 'danger' | 'default'> = {
  lobby:     'default',
  active:    'success',
  paused:    'warning',
  completed: 'info',
  archived:  'danger',
}

// ── Create Campaign Modal Content ──────────────────────────────────────────
interface CreateCampaignFormProps {
  onClose:  () => void
  onCreate: (campaign: Campaign) => void
}

function CreateCampaignForm({ onClose, onCreate }: CreateCampaignFormProps): React.ReactElement {
  const [title,           setTitle]           = useState('')
  const [description,     setDescription]     = useState('')
  const [rpgSystem,       setRpgSystem]       = useState('D&D 5e')
  const [aiPlayersCount,  setAiPlayersCount]  = useState(0)
  const [isLoading,       setIsLoading]       = useState(false)
  const [error,           setError]           = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    if (!title.trim()) { setError('Campaign title is required.'); return }

    setIsLoading(true)
    setError(null)
    try {
      const payload: CreateCampaignRequest = {
        title:            title.trim(),
        description:      description.trim(),
        rpg_system:       rpgSystem,
        ai_players_count: aiPlayersCount,
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
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="flex items-start gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      <Input
        label="Campaign Title"
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="The Lost Mines of Phandelver"
        maxLength={120}
        autoFocus
      />

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

      <div>
        <label className="label-rune flex items-center gap-1.5">
          <Bot className="w-3.5 h-3.5 text-amber-600" />
          AI Players at the Table
        </label>
        <div className="flex gap-2 mt-1.5">
          {([0, 1, 2, 3, 4] as const).map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setAiPlayersCount(n)}
              className={`flex-1 py-2 rounded border text-sm font-serif transition-all ${
                aiPlayersCount === n
                  ? 'bg-amber-600/30 border-amber-600/60 text-amber-300'
                  : 'bg-transparent border-slate-700 text-slate-500 hover:border-amber-700/50 hover:text-slate-300'
              }`}
            >
              {n === 0 ? 'None' : n}
            </button>
          ))}
        </div>
        {aiPlayersCount > 0 && (
          <p className="text-slate-500 text-xs mt-1.5 font-serif italic">
            {aiPlayersCount} AI companion{aiPlayersCount > 1 ? 's' : ''} will be generated and added to the campaign.
          </p>
        )}
      </div>

      <div className="flex gap-3 pt-2">
        <Button
          type="button"
          variant="ghost"
          onClick={onClose}
          disabled={isLoading}
          className="flex-1 justify-center"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={isLoading}
          leftIcon={<Plus className="w-4 h-4" />}
          className="flex-1 justify-center"
        >
          {isLoading ? 'Creating…' : 'Create Campaign'}
        </Button>
      </div>
    </form>
  )
}

// ── Campaign Card ──────────────────────────────────────────────────────────
interface CampaignCardProps {
  campaign:   Campaign
  onDelete:   (id: string) => Promise<void>
  isDeleting: boolean
}

function CampaignCard({ campaign, onDelete, isDeleting }: CampaignCardProps): React.ReactElement {
  const navigate = useNavigate()

  return (
    <div className="card-rune p-5 hover:border-amber-600/60 transition-all duration-200 group">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-amber-400 text-lg truncate group-hover:text-amber-300 transition-colors">
            {campaign.title}
          </h3>
          <p className="text-slate-500 text-xs mt-0.5 font-serif">{campaign.rpg_system}</p>
        </div>
        <Badge variant={STATUS_BADGE_VARIANT[campaign.status]} className="shrink-0">
          {STATUS_LABELS[campaign.status]}
        </Badge>
      </div>

      {campaign.description && (
        <p className="text-slate-400 text-sm leading-relaxed line-clamp-2 mb-4 font-serif italic">
          {truncate(campaign.description, 120)}
        </p>
      )}

      <div className="flex items-center gap-4 text-slate-500 text-xs mb-4">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formatDate(campaign.updated_at)}
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
        <Button
          variant="primary"
          size="sm"
          leftIcon={<Sword className="w-3.5 h-3.5" />}
          onClick={() => navigate(`/lobby/${campaign.id}`)}
          className="flex-1 justify-center"
        >
          Play
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/campaign/${campaign.id}/characters`)}
          className="px-3"
          title="Characters"
        >
          <Users className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/campaign/${campaign.id}/map`)}
          className="px-3"
          title="World Map"
        >
          <Map className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          isLoading={isDeleting}
          onClick={() => void onDelete(String(campaign.id))}
          className="px-3 text-red-400 hover:text-red-300 hover:border-red-700/50"
          title="Delete campaign"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function Dashboard(): React.ReactElement {
  const { user }                           = useAuth()
  const navigate                           = useNavigate()
  const [campaigns,    setCampaigns]       = useState<Campaign[]>([])
  const [isLoading,    setIsLoading]       = useState(true)
  const [error,        setError]           = useState<string | null>(null)
  const [showCreate,   setShowCreate]      = useState(false)
  const [filterStatus, setFilterStatus]    = useState<CampaignStatus | 'all'>('all')
  const [deletingId,   setDeletingId]      = useState<string | null>(null)

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

  async function handleDeleteCampaign(id: string): Promise<void> {
    if (!window.confirm('Delete this campaign? This action cannot be undone.')) {
      return
    }

    setError(null)
    setDeletingId(id)

    try {
      await campaignApi.delete(id)
      setCampaigns((current) => current.filter((campaign) => String(campaign.id) !== id))
    } catch {
      setError('Unable to delete campaign. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <AppLayout>
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
        <Button
          variant="primary"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => setShowCreate(true)}
          className="shrink-0"
        >
          New Campaign
        </Button>
      </div>

      {/* Filter tabs */}
      {campaigns.length > 0 && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {(['all', 'lobby', 'active', 'paused', 'completed', 'archived'] as const).map((s) => (
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
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
            <Button
              variant="primary"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => setShowCreate(true)}
            >
              Create First Campaign
            </Button>
          )}
        </div>
      )}

      {/* Campaign grid */}
      {!isLoading && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onDelete={handleDeleteCampaign}
              isDeleting={deletingId === String(campaign.id)}
            />
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

      {/* Create modal */}
      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        title="New Campaign"
        size="md"
      >
        <CreateCampaignForm
          onClose={() => setShowCreate(false)}
          onCreate={(campaign) => {
            setShowCreate(false)
            navigate(`/lobby/${campaign.id}`)
          }}
        />
      </Modal>
    </AppLayout>
  )
}
