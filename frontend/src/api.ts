import type { AuthStartResponse, CHPPStatus, SquadResponse, SyncResponse } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // A non-JSON upstream failure still gets a useful status-based message.
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export const api = {
  status: () => request<CHPPStatus>('/api/chpp/status'),
  squad: () => request<SquadResponse>('/api/squad'),
  sync: () => request<SyncResponse>('/api/chpp/sync', { method: 'POST' }),
  startAuth: () => request<AuthStartResponse>('/api/chpp/auth/start', { method: 'POST' }),
}
