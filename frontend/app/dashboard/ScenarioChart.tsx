'use client'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js'
import type { MathData } from '@/lib/types'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend)

function formatEur(value: number): string {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

interface Props {
  mathData: MathData
}

export function ScenarioChart({ mathData }: Props) {
  const data = {
    labels: mathData.labels.map(y => `Anno ${y}`),
    datasets: [
      {
        label: 'Sicuro 3.5%',
        data: mathData.sicuro,
        borderColor: '#86efac',
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 2,
      },
      {
        label: 'Bilanciato 5%',
        data: mathData.bilanciato,
        borderColor: '#4ade80',
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 2,
      },
      {
        label: 'Crescita 7%',
        data: mathData.crescita,
        borderColor: '#059669',
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 2,
      },
      {
        label: 'Inflazione 2.5%',
        data: mathData.inflazione,
        borderColor: '#94a3b8',
        borderDash: [5, 5],
        backgroundColor: 'transparent',
        tension: 0.1,
        pointRadius: 0,
      },
    ],
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { position: 'top' as const },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
            `${ctx.dataset.label}: ${formatEur(ctx.parsed.y ?? 0)}`,
        },
      },
    },
    scales: {
      y: {
        ticks: {
          callback: (value: number | string) => formatEur(Number(value)),
        },
      },
    },
  }

  return (
    <div className="chart-container">
      <Line data={data} options={options} />
    </div>
  )
}
