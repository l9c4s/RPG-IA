import { apiClient, apiClientMultipart } from './client'
import type { KnowledgeStats, PDFSource } from '../types'

export const knowledgeApi = {
  getStats: () =>
    apiClient.get<KnowledgeStats>('/books/knowledge/stats'),

  listSources: () =>
    apiClient.get<PDFSource[]>('/books/sources'),

  getSource: (id: string) =>
    apiClient.get<PDFSource>(`/books/sources/${id}/status`),

  upload: (formData: FormData) =>
    apiClientMultipart.post<PDFSource>('/books/upload', formData),

  deleteSource: (id: string) =>
    apiClient.delete(`/books/sources/${id}`),
}
