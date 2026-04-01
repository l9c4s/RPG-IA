import { apiClient, api } from './client'
import type { Campaign, CreateCampaignRequest, CampaignStatus, Location, Generated8BitCharacter } from '../types'

export const campaignApi = {
  list: () =>
    apiClient.get<Campaign[]>('/campaigns/'),

  get: (id: string) =>
    apiClient.get<Campaign>(`/campaigns/${id}`),

  create: (data: CreateCampaignRequest) =>
    apiClient.post<Campaign>('/campaigns/', data),

  delete: (id: string | number) =>
    apiClient.delete(`/campaigns/${id}`),

  updateStatus: (id: string, status: CampaignStatus) =>
    apiClient.patch<{ id: string; status: CampaignStatus }>(`/campaigns/${id}/status`, { status }),

  getState: (id: string) =>
    apiClient.get(`/campaigns/${id}/state`),

  getSessions: (id: string) =>
    apiClient.get(`/campaigns/${id}/sessions`),

  generateMap: (id: string) =>
    apiClient.post<{ locations: Location[] }>(`/campaigns/${id}/generate-map`, {}),

  generate8BitCharacter: (id: string, description: string) =>
    api.post<Generated8BitCharacter>(`/campaigns/${id}/generate-character-8bit`, { description }),

  getLocations: (id: string) =>
    apiClient.get<Location[]>(`/campaigns/${id}/locations`),
}
