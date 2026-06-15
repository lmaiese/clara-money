'use client'
import { useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { apiFetch, ApiError } from '@/lib/api'

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      router.replace('/auth?reset=success')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore di rete')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <main className="auth-layout">
        <div className="auth-card">
          <p className="form-error">
            Link non valido.{' '}
            <a href="/auth/forgot-password">Richiedi un nuovo link.</a>
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <h1>Nuova password</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Nuova password (min. 8 caratteri)"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Salvataggio...' : 'Salva nuova password'}
          </button>
        </form>
      </div>
    </main>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  )
}
