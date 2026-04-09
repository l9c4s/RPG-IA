/**
 * RoundPanel — painel de round coletivo com d20 de iniciativa.
 *
 * Exibe:
 * 1. Fase de coleta: input de ação + botão "Passar"
 * 2. Initiative board: tabela com d20 de cada jogador após todos submeterem
 * 3. Narração do GM em tempo real por ação
 */

import React, { useState } from 'react'
import { Sword, SkipForward, Dice6, Loader2, CheckCircle2, Clock } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface InitiativeEntry {
  character_name: string
  is_ai: boolean
  d20_roll: number
  initiative_order: number
  action_text: string | null
  is_pass: boolean
  character_id: string | null
}

export interface GMRoundResponse {
  initiative_order: number
  character_name: string
  action_text: string | null
  gm_text: string
  roll_results: { expr: string; result: number }[]
  gm_rolled_dice: boolean
  outcome_roll: number | null
}

export type RoundPhase =
  | 'idle'
  | 'collecting'
  | 'resolving'
  | 'gm_processing'
  | 'completed'

export interface RoundState {
  roundId: string
  roundNumber: number
  phase: RoundPhase
  submittedCount: number
  expectedCount: number
  myActionSubmitted: boolean
  initiative: InitiativeEntry[]
  gmResponses: GMRoundResponse[]
}

interface RoundPanelProps {
  round: RoundState
  characterName: string
  onSubmitAction: (actionText: string | null, isPass: boolean) => void
  onStartRound: () => void
  isStarting: boolean
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function SubmittedCountBubbles({
  submitted,
  expected,
}: {
  submitted: number
  expected: number
}): React.ReactElement {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: expected }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full transition-all ${
            i < submitted ? 'bg-amber-400' : 'bg-slate-600'
          }`}
        />
      ))}
      <span className="text-slate-400 text-xs ml-1">
        {submitted}/{expected}
      </span>
    </div>
  )
}

function InitiativeBoard({ entries }: { entries: InitiativeEntry[] }): React.ReactElement {
  return (
    <div className="space-y-1.5">
      {entries.map((entry) => {
        const isCrit   = entry.d20_roll === 20
        const isFumble = entry.d20_roll === 1

        return (
          <div
            key={entry.character_name}
            className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/40"
          >
            {/* Initiative number */}
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-amber-400">
              {entry.initiative_order}
            </div>

            {/* d20 badge */}
            <div
              className={`flex-shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold border ${
                isCrit
                  ? 'bg-amber-900/60 border-amber-500/60 text-amber-300'
                  : isFumble
                  ? 'bg-red-900/60 border-red-500/60 text-red-300'
                  : entry.is_pass
                  ? 'bg-slate-700/60 border-slate-600/40 text-slate-400'
                  : 'bg-slate-700/60 border-slate-600/60 text-slate-200'
              }`}
            >
              <Dice6 className="w-3 h-3" />
              {entry.d20_roll}
            </div>

            {/* Character + action */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-200 truncate">
                  {entry.character_name}
                </span>
                {entry.is_ai && (
                  <span className="flex-shrink-0 text-xs bg-purple-900/60 border border-purple-700/40 text-purple-300 px-1.5 py-0.5 rounded">
                    IA
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5 font-serif italic">
                {entry.is_pass ? 'passou a vez' : (entry.action_text ?? '…')}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function GMResponseCard({ resp }: { resp: GMRoundResponse }): React.ReactElement {
  return (
    <div className="p-3 rounded-lg border border-amber-700/30 bg-amber-950/20">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-amber-400 text-xs font-serif font-semibold">
          [{resp.initiative_order}] {resp.character_name}
        </span>
        {resp.gm_rolled_dice && resp.outcome_roll !== null && (
          <span className="text-xs bg-slate-700/60 border border-slate-600/40 text-slate-300 px-1.5 py-0.5 rounded font-bold">
            🎲 {resp.outcome_roll}
          </span>
        )}
      </div>
      <p className="text-slate-200 text-sm font-serif leading-relaxed">
        {resp.gm_text}
      </p>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function RoundPanel({
  round,
  characterName,
  onSubmitAction,
  onStartRound,
  isStarting,
}: RoundPanelProps): React.ReactElement {
  const [actionText, setActionText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(isPass: boolean): Promise<void> {
    if (isSubmitting) return
    if (!isPass && !actionText.trim()) return
    setIsSubmitting(true)
    try {
      onSubmitAction(isPass ? null : actionText.trim(), isPass)
      setActionText('')
    } finally {
      setIsSubmitting(false)
    }
  }

  // ── Idle: botão para iniciar round ──────────────────────────────────────
  if (round.phase === 'idle' || round.phase === 'completed') {
    return (
      <div className="p-4 border-t border-slate-700/50 bg-slate-900/60">
        {round.phase === 'completed' && (
          <p className="text-slate-400 text-xs font-serif italic mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
            Round {round.roundNumber} concluído.
          </p>
        )}
        <button
          type="button"
          onClick={onStartRound}
          disabled={isStarting}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-amber-700/20 border border-amber-600/40 text-amber-300 hover:bg-amber-700/30 transition-all text-sm font-serif font-semibold disabled:opacity-50"
        >
          {isStarting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sword className="w-4 h-4" />
          )}
          {isStarting ? 'Iniciando round…' : 'Iniciar Round Coletivo'}
        </button>
      </div>
    )
  }

  // ── Collecting: aguardando ações ─────────────────────────────────────────
  if (round.phase === 'collecting') {
    return (
      <div className="p-4 border-t border-slate-700/50 bg-slate-900/60 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span className="text-amber-400 text-xs font-serif font-semibold">
              Round {round.roundNumber} — Declare sua ação
            </span>
          </div>
          <SubmittedCountBubbles
            submitted={round.submittedCount}
            expected={round.expectedCount}
          />
        </div>

        {round.myActionSubmitted ? (
          /* Já submeteu — aguardando outros */
          <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-slate-800/60 border border-slate-700/40">
            <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
            <span className="text-slate-400 text-sm font-serif italic">
              Ação enviada! Aguardando outros jogadores…
            </span>
          </div>
        ) : (
          /* Formulário de ação */
          <>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">
                O que <span className="text-amber-300">{characterName}</span> faz?
              </label>
              <textarea
                value={actionText}
                onChange={(e) => setActionText(e.target.value)}
                placeholder="Descreva sua ação… ex: Ataco o goblin com minha espada!"
                className="input-dark resize-none h-16 text-sm w-full"
                maxLength={500}
                disabled={isSubmitting}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void handleSubmit(false)
                  }
                }}
              />
              <p className="text-slate-600 text-xs text-right mt-0.5">
                {actionText.length}/500
              </p>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void handleSubmit(true)}
                disabled={isSubmitting}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-600/60 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-all text-sm disabled:opacity-50"
              >
                <SkipForward className="w-4 h-4" />
                Passar
              </button>
              <button
                type="button"
                onClick={() => void handleSubmit(false)}
                disabled={isSubmitting || !actionText.trim()}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-amber-700/30 border border-amber-600/50 text-amber-300 hover:bg-amber-700/40 transition-all text-sm font-semibold disabled:opacity-50"
              >
                {isSubmitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sword className="w-4 h-4" />
                )}
                {isSubmitting ? 'Enviando…' : 'Agir'}
              </button>
            </div>
          </>
        )}
      </div>
    )
  }

  // ── Resolving / GM Processing / Completed: mostra initiative board ───────
  return (
    <div className="p-4 border-t border-slate-700/50 bg-slate-900/60 space-y-3 max-h-80 overflow-y-auto">
      {/* Initiative board */}
      {round.initiative.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Dice6 className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-amber-400 text-xs font-serif font-semibold">
              Iniciativa — Round {round.roundNumber}
            </span>
            {round.phase === 'gm_processing' && (
              <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin ml-auto" />
            )}
          </div>
          <InitiativeBoard entries={round.initiative} />
        </div>
      )}

      {/* GM responses (aparecem conforme chegam via WS) */}
      {round.gmResponses.length > 0 && (
        <div className="space-y-2">
          <span className="text-amber-400 text-xs font-serif font-semibold">Narração do Mestre</span>
          {round.gmResponses.map((r) => (
            <GMResponseCard key={r.initiative_order} resp={r} />
          ))}
        </div>
      )}

      {round.phase === 'resolving' && (
        <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-slate-800/60 border border-slate-700/40">
          <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
          <span className="text-slate-400 text-sm font-serif italic">Rolando dados de iniciativa…</span>
        </div>
      )}
    </div>
  )
}
