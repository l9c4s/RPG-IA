import { apiClient } from './client'
import type { ChatMessage } from '../types'

export const sessionApi = {
  getOrCreate: (campaignId: string) =>
    apiClient.post<{ session_id: string }>(`/session/campaigns/${campaignId}/session`),

  getHistory: (sessionId: string) =>
    apiClient.get<ChatMessage[]>(`/session/sessions/${sessionId}/messages`),

  sendAction: (sessionId: string, action: Record<string, unknown>) =>
    apiClient.post<unknown>(`/session/sessions/${sessionId}/action`, action),
}
