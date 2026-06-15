import { render, screen } from '@testing-library/react'
import { SourcesSection } from '../app/dashboard/SourcesSection'

const SOURCES = [
  { title: 'relazione-annuale-2024 [3/47]', source: 'BdI' },
  { title: 'guida-mifid2 [5/23]', source: 'CONSOB' },
]

it('shows source titles and badges when sources provided', () => {
  render(<SourcesSection sources={SOURCES} />)
  expect(screen.getByText(/relazione-annuale-2024/)).toBeInTheDocument()
  expect(screen.getByText('BdI')).toBeInTheDocument()
  expect(screen.getByText('CONSOB')).toBeInTheDocument()
})

it('renders nothing when sources is null', () => {
  const { container } = render(<SourcesSection sources={null} />)
  expect(container.firstChild).toBeNull()
})
