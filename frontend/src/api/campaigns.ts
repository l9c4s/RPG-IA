import { apiClient } from './client'
import type { Campaign, CreateCampaignRequest } from '../types'

export const campaignApi = {
  list: () =>
    apiClient.get<Campaign[]>('/campaigns/'),

  get: (id: string) =>
    apiClient.get<Campaign>(`/campaigns/${id}`),

  create: (data: CreateCampaignRequest) =>
    apiClient.post<Campaign>('/campaigns/', data),

  delete: (id: string) =>
    apiClient.delete(`/campaigns/${id}`),

  getState: (id: string) =>
    apiClient.get(`/campaigns/${id}/state`),

  getSessions: (id: string) =>
    apiClient.get(`/campaigns/${id}/sessions`),
}
