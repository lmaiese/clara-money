'use client'
import { useState } from 'react'
import { apiFetch } from '@/lib/api'

interface PaywallGateProps {
  label: string
  rate: string
  risk: string
  color: string
  relativeValue: string
}

export function PaywallGate({ label, rate, risk, color, relativeValue }: PaywallGateProps) {
  return (
    <div className="scenario-card scenario-card--locked" style={{ borderTopColor: color }}>
      <div className="scenario-label">{label} · {rate}</div>
      <div className="scenario-value scenario-value--blurred">€ ••••••</div>
      <div className="scenario-risk">Rischio: {risk}</div>
      <div className="paywall-teaser" style={{ color }}>{relativeValue} vs Sicuro</div>
      <span className="paywall-pill">🔒 Pro</span>
    </div>
  )
}

export function PaywallBanner() {
  const [loading, setLoading] = useState(false)

  async function handleUpgrade() {
    setLoading(true)
    try {
      const { checkout_url } = await apiFetch<{ checkout_url: string }>('/billing/checkout', {
        method: 'POST',
      })
      window.location.href = checkout_url
    } catch {
      setLoading(false)
    }
  }

  return (
    <div className="paywall-banner">
      <p>
        Sblocca tutti gli scenari con <strong>Clara Pro</strong> — 8 €/mese
      </p>
      <button className="btn-primary" onClick={handleUpgrade} disabled={loading}>
        {loading ? 'Caricamento...' : 'Passa a Pro'}
      </button>
    </div>
  )
}
