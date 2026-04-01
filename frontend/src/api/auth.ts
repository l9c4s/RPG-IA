import { apiClient } from './client'
import type { Token, User, LoginRequest, RegisterRequest } from '../types'

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<Token>('/auth/login', data),

  register: (data: RegisterRequest) =>
    apiClient.post<User | Token>('/auth/register', data),

  me: () =>
    apiClient.get<User>('/auth/me'),
}
