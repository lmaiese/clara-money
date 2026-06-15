import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useWizard } from '@/app/onboarding/useWizard'

const mockFetch = vi.fn()
global.fetch = mockFetch

function mockProfile(onboarding_step: number) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ onboarding_step }),
  })
}

function mockPatchOk() {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ onboarding_step: 1 }),
  })
}

function mockPatchError(status: number) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    json: async () => ({ detail: 'error' }),
  })
}

beforeEach(() => vi.clearAllMocks())

describe('useWizard', () => {
  it('starts at onboarding_step from server', async () => {
    mockProfile(2)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.currentStep).toBe(2)
  })

  it('advances step on successful PATCH', async () => {
    mockProfile(0)
    mockPatchOk()
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.next({ age: 30, monthly_income: 2000 }) })
    expect(result.current.currentStep).toBe(1)
    expect(result.current.error).toBeNull()
  })

  it('sets error on network failure without advancing', async () => {
    mockProfile(0)
    mockPatchError(500)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.next({ age: 30, monthly_income: 2000 }) })
    expect(result.current.currentStep).toBe(0)
    expect(result.current.error).toBe('Errore di rete, riprova')
  })

  it('back() decrements step without PATCH', async () => {
    mockProfile(2)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    act(() => { result.current.back() })
    expect(result.current.currentStep).toBe(1)
    expect(mockFetch).toHaveBeenCalledTimes(1) // solo il GET iniziale
  })
})
