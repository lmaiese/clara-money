import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDashboard } from '../app/dashboard/useDashboard'
import type { MathData, Narratives } from '../lib/types'

const MATH_DATA: MathData = {
  sicuro: [10000, 10350],
  bilanciato: [10000, 10500],
  crescita: [10000, 10700],
  inflazione: [10000, 10250],
  labels: [0, 1],
}

const NARRATIVES: Narratives = {
  intro: 'Intro',
  sicuro: 'Sicuro text',
  bilanciato: 'Bilanciato text',
  crescita: 'Crescita text',
}

function mockResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  )
}

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

it('starts in loading state', () => {
  global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
  const { result } = renderHook(() => useDashboard())
  expect(result.current.status).toBe('loading')
})

it('transitions to math_ready after POST /scenarios/generate', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce(mockResponse({
      scenario_id: 'abc', math_data: MATH_DATA,
      narratives: null, narrative_ready: false, generated_at: new Date().toISOString()
    }))
    .mockReturnValue(new Promise(() => {}))

  const { result } = renderHook(() => useDashboard())
  await act(async () => { await vi.runAllTimersAsync() })
  expect(result.current.status).toBe('math_ready')
  if (result.current.status === 'math_ready') {
    expect(result.current.mathData.labels).toEqual([0, 1])
  }
})

it('transitions to narrative_ready when poll returns narrative_ready=true', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce(mockResponse({
      scenario_id: 'abc', math_data: MATH_DATA,
      narratives: null, narrative_ready: false, generated_at: new Date().toISOString()
    }))
    .mockResolvedValue(mockResponse({
      scenario_id: 'abc', math_data: MATH_DATA,
      narratives: NARRATIVES, narrative_ready: true, generated_at: new Date().toISOString()
    }))

  const { result } = renderHook(() => useDashboard())
  await act(async () => { await vi.runAllTimersAsync() })
  expect(result.current.status).toBe('narrative_ready')
  if (result.current.status === 'narrative_ready') {
    expect(result.current.narratives.intro).toBe('Intro')
  }
})

it('transitions to error if POST /scenarios/generate fails', async () => {
  global.fetch = vi.fn().mockResolvedValue(
    mockResponse({ detail: 'Profile not complete' }, 400)
  )

  const { result } = renderHook(() => useDashboard())
  await act(async () => { await vi.runAllTimersAsync() })
  expect(result.current.status).toBe('error')
})
