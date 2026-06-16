'use client'
import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/api'

function WaitlistForm({ variant }: { variant: 'hero' | 'bottom' }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'duplicate' | 'error'>('idle')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('loading')
    try {
      await apiFetch('/waitlist', { method: 'POST', body: JSON.stringify({ email }) })
      setStatus('success')
    } catch (err) {
      setStatus(err instanceof ApiError && err.status === 409 ? 'duplicate' : 'error')
    }
  }

  if (status === 'success') {
    return (
      <p className={`waitlist-success${variant === 'bottom' ? ' waitlist-success--bottom' : ''}`}>
        Sei in lista. Ti avvisiamo presto.
      </p>
    )
  }

  return (
    <div>
      <form className={`waitlist-form waitlist-form--${variant}`} onSubmit={handleSubmit}>
        <label htmlFor={`waitlist-email-${variant}`} className="sr-only">Indirizzo email</label>
        <input
          id={`waitlist-email-${variant}`}
          type="email"
          placeholder="La tua email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <button
          type="submit"
          className={variant === 'hero' ? 'btn-primary' : 'btn-white'}
          disabled={status === 'loading'}
        >
          {status === 'loading' ? 'Caricamento...' : 'Iscriviti'}
        </button>
      </form>
      {status === 'duplicate' && <p className="waitlist-form-error">Email già registrata.</p>}
      {status === 'error' && <p className="waitlist-form-error">Errore di rete, riprova.</p>}
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      <nav className="landing-nav">
        <div className="brand">
          <span className="brand-icon">C</span>
          <span className="brand-name">Clara</span>
        </div>
        <a href="/auth" className="nav-login">Hai già un account? Accedi →</a>
      </nav>

      <section className="landing-hero">
        <span className="hero-badge">Beta in arrivo</span>
        <h1>I tuoi risparmi meritano un <span className="hero-accent">piano vero</span></h1>
        <p className="hero-sub">
          Clara analizza la tua situazione e mostra matematicamente cosa succede
          ai tuoi soldi in 3 scenari alternativi.
        </p>
        <WaitlistForm variant="hero" />
        <p className="hero-note">Gratis. Senza carta di credito. Ti avvisiamo quando apriamo.</p>
      </section>

      <section className="landing-section">
        <h2 className="landing-section-title">Perché Clara</h2>
        <p className="landing-section-sub">Niente consulenti bancari. Niente prodotti da vendere. Solo matematica.</p>
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="3" y="12" width="4" height="8" rx="1"/>
                <rect x="10" y="7" width="4" height="13" rx="1"/>
                <rect x="17" y="3" width="4" height="17" rx="1"/>
              </svg>
            </div>
            <h3>3 scenari reali</h3>
            <p>Sicuro, bilanciato, crescita — con rendimenti storici documentati, anno per anno fino al tuo orizzonte.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 3l1.88 5.12L19 10l-5.12 1.88L12 17l-1.88-5.12L5 10l5.12-1.88z"/>
                <path d="M19 17l.75 1.75L21.5 19.5l-1.75.75L19 22l-.75-1.75L16.5 19.5l1.75-.75z"/>
                <path d="M5 4.5l.63 1.37L7 6.5l-1.37.63L5 8.5l-.63-1.5L3 6.5l1.37-.63z"/>
              </svg>
            </div>
            <h3>Narrativa AI</h3>
            <p>Claude (Anthropic) spiega ogni scenario in italiano semplice, adattato alla tua età e ai tuoi obiettivi.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
            </div>
            <h3>Aggiornamento mensile</h3>
            <p>Ogni mese ricevi un digest con i tuoi scenari aggiornati e il delta rispetto al mese precedente.</p>
          </div>
        </div>
      </section>

      <section className="landing-section landing-section--alt">
        <h2 className="landing-section-title">Come funziona</h2>
        <p className="landing-section-sub">5 minuti per avere il tuo piano finanziario</p>
        <div className="steps-grid">
          <div className="how-step">
            <div className="step-num">1</div>
            <h3>Racconti la tua situazione</h3>
            <p>Reddito, spese, risparmi, orizzonte. 5 domande, niente di personale.</p>
          </div>
          <div className="how-step">
            <div className="step-num">2</div>
            <h3>Clara calcola i tuoi scenari</h3>
            <p>Matematica compound mensile su 3 strategie: liquidità, obbligazionario, azionario.</p>
          </div>
          <div className="how-step">
            <div className="step-num">3</div>
            <h3>Capisci davvero</h3>
            <p>Grafici chiari, narrativa AI, normativa italiana aggiornata inclusa.</p>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <h2 className="landing-section-title">Prezzi</h2>
        <p className="landing-section-sub">Inizia gratis, passa a Pro quando sei pronto</p>
        <div className="pricing-grid">
          <div className="plan-card">
            <div className="plan-name">Free</div>
            <div className="plan-price">€0 <span>/ sempre</span></div>
            <ul className="plan-features">
              <li>Scenario Sicuro (liquidità)</li>
              <li>Onboarding 5 domande</li>
              <li>Dashboard con grafico</li>
            </ul>
          </div>
          <div className="plan-card plan-card--pro">
            <div className="plan-badge">PRO</div>
            <div className="plan-name">Pro</div>
            <div className="plan-price">€8 <span>/ mese</span></div>
            <ul className="plan-features">
              <li>Tutti e 3 gli scenari</li>
              <li>Digest mensile con delta</li>
              <li>Narrativa AI personalizzata</li>
              <li>Normativa italiana (RAG)</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="landing-cta">
        <h2>Unisciti alla waitlist</h2>
        <p>Sii tra i primi a scoprire cosa fare con i tuoi risparmi.</p>
        <WaitlistForm variant="bottom" />
      </section>

      <footer className="landing-footer">
        <p>© 2026 Clara · <a href="mailto:support@claramoney.it">support@claramoney.it</a> · Solo educazione finanziaria, non consulenza</p>
      </footer>
    </>
  )
}
