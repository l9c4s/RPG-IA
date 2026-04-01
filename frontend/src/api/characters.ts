import { apiClient } from './client'
import type { Character, CharacterStatus } from '../types'

export const characterApi = {
  list: (campaignId: string) =>
    apiClient.get<Character[]>(`/characters/?campaign_id=${campaignId}`),

  get: (id: string) =>
    apiClient.get<Character>(`/characters/${id}`),

  create: (data: Partial<Character>) =>
    apiClient.post<Character>('/characters/', data),

  update: (id: string, data: Partial<Character>) =>
    apiClient.put<Character>(`/characters/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/characters/${id}`),

  getStatus: (id: string) =>
    apiClient.get<CharacterStatus>(`/characters/${id}/status`),

  updateStatus: (id: string, data: Partial<CharacterStatus>) =>
    apiClient.patch<CharacterStatus>(`/characters/${id}/status`, data),

  addAiCompanion: (campaignId: string) =>
    apiClient.post<Character>('/characters/ai-companion', { campaign_id: campaignId }),
}
