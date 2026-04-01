import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Sword, Users, Plus, AlertCircle, ChevronLeft,
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { AppLayout } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import type { Campaign, Character } from '../types'

export default function Lobby(): React.ReactElement {
  const { id: campaignId }         = useParams<{ id: string }>()
  const { user }                   = useAuth()
  const navigate                   = useNavigate()

  const [campaign,    setCampaign]    = useState<Campaign | null>(null)
  const [characters,  setCharacters]  = useState<Character[]>([])
  const [isLoading,   setIsLoading]   = useState(true)
  const [error,       setError]       = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!campaignId) return
    setIsLoading(true)
    setError(null)
    try {
      const [campaignData, charData] = await Promise.all([
        api.get<Campaign>(`/campaigns/${campaignId}`),
        api.get<Character[]>(`/campaigns/${campaignId}/characters`),
      ])
      setCampaign(campaignData)
      setCharacters(charData)
    } catch {
      setError('Failed to load lobby data.')
    } finally {
      setIsLoading(false)
    }
  }, [campaignId])

  useEffect(() => { void fetchData() }, [fetchData])

  const myCharacter = characters.find((c) => c.player_id === user?.id)

  return (
    <AppLayout>
      {/* Back navigation */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
          onClick={() => navigate('/dashboard')}
        >
          Dashboard
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Spinner size="lg" />
          <p className="text-slate-400 font-serif italic text-sm">
            Preparing the keep…
          </p>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-lg px-5 py-4 text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
          <button
            onClick={fetchData}
            className="ml-auto text-xs underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      ) : campaign ? (
        <div className="space-y-6 max-w-3xl mx-auto">
          {/* Campaign header */}
          <div className="card-rune p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-serif text-amber-400 mb-1">
                  {campaign.title}
                </h1>
                <p className="text-slate-400 text-sm font-serif">{campaign.rpg_system}</p>
                {campaign.description && (
                  <p className="text-slate-300 text-sm italic mt-2 leading-relaxed">
                    {campaign.description}
                  </p>
                )}
              </div>
              <Badge
                variant={
                  campaign.status === 'active'    ? 'success' :
                  campaign.status === 'paused'    ? 'warning' :
                  campaign.status === 'completed' ? 'info'    : 'danger'
                }
                className="shrink-0"
              >
                {campaign.status}
              </Badge>
            </div>
          </div>

          {/* Players */}
          <div className="card-rune p-6">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-4 h-4 text-amber-500" />
              <h2 className="font-serif text-amber-400 text-lg">
                Party Members
              </h2>
            </div>

            {characters.length === 0 ? (
              <p className="text-slate-500 font-serif italic text-sm">
                No characters in this campaign yet.
              </p>
            ) : (
              <div className="space-y-3">
                {characters.map((char) => (
                  <div
                    key={char.id}
                    className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/40"
                  >
                    <div>
                      <p className="text-slate-200 font-semibold text-sm">{char.name}</p>
                      <p className="text-slate-500 text-xs">
                        Level {char.level} {char.character_class} · {char.race}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {char.player_id === user?.id && (
                        <Badge variant="success">You</Badge>
                      )}
                      <span className="text-slate-400 text-xs">
                        HP {char.status.hp_current}/{char.status.hp_max}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="primary"
              leftIcon={<Sword className="w-4 h-4" />}
              onClick={() => navigate(`/campaign/${campaignId}`)}
              className="flex-1 justify-center"
            >
              Enter Session
            </Button>
            {!myCharacter && (
              <Button
                variant="ghost"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => navigate(`/campaign/${campaignId}/characters`)}
                className="flex-1 justify-center"
              >
                Create Character
              </Button>
            )}
          </div>
        </div>
      ) : null}
    </AppLayout>
  )
}
