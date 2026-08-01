import { request } from './http'
import type { Message, TokenPair, UserRead } from '../types'

export const authApi = {
  login: (email: string, password: string) =>
    request<TokenPair>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, full_name: string) =>
    request<TokenPair>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),
  me: () => request<UserRead>('/auth/me'),
  logout: (refresh_token: string) =>
    request<Message>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token }),
    }),
}
