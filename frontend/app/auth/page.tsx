'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, ApiError } from '@/lib/api'

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'register' | 'login'>('register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiFetch(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      router.replace('/onboarding')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? 'Email già registrata — accedi.' : err.message)
      } else {
        setError('Errore di rete, riprova.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-icon">C</span>
          <h1>Clara</h1>
        </div>
        <p className="auth-subtitle">
          {mode === 'register' ? 'Scopri cosa fare con i tuoi risparmi.' : 'Bentornato.'}
        </p>
        <div className="auth-tabs">
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            Registrati
          </button>
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            Accedi
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password (min. 8 caratteri)" value={password}
            onChange={e => setPassword(e.target.value)} required />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Caricamento...' : mode === 'register' ? 'Inizia gratis' : 'Accedi'}
          </button>
          {mode === 'login' && (
            <a href="/auth/forgot-password" className="forgot-link">
              Password dimenticata?
            </a>
          )}
        </form>
      </div>
    </main>
  )
}
