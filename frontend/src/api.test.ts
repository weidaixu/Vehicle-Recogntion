import { describe, expect, it } from 'vitest'
import { ApiError, requestJson } from './api'

describe('requestJson', () => {
  it('returns parsed JSON for a successful response', async () => {
    const result = await requestJson<{ ready: boolean }>('/api/status', {}, async () =>
      new Response(JSON.stringify({ ready: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    expect(result).toEqual({ ready: true })
  })

  it('surfaces the backend detail when a request fails', async () => {
    await expect(requestJson('/api/fail', {}, async () =>
      new Response(JSON.stringify({ detail: '图片无法解码' }), { status: 422, headers: { 'Content-Type': 'application/json' } }),
    )).rejects.toEqual(new ApiError('图片无法解码', 422))
  })
})
