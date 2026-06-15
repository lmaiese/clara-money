'use client'
import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore di rete')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <main className="auth-layout">
        <div className="auth-card">
          <p>Controlla la tua email — ti abbiamo inviato un link di reset.</p>
          <a href="/auth">Torna al login</a>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <h1>Reimposta password</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Invio...' : 'Invia link di reset'}
          </button>
        </form>
        <a href="/auth">Torna al login</a>
      </div>
    </main>
  )
}
