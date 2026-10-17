import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Alert } from '../api/portfolio'
import { PortfolioAlerts } from './PortfolioAlerts'
import { ProgressBar } from './ui'

const alerts: Alert[] = [
  { kind: 'rebalance', severity: 'warning', goal_id: 11, goal_name: 'New car', message: 'Equity is 100% against 7%.' },
  { kind: 'no_recommendation', severity: 'info', goal_id: 12, goal_name: 'Trip', message: 'No recommendation yet.' },
]

describe('PortfolioAlerts', () => {
  it('links each alert to the page that fixes it', () => {
    render(
      <MemoryRouter>
        <PortfolioAlerts alerts={alerts} />
      </MemoryRouter>,
    )
    expect(screen.getByText('New car:')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See what to move' })).toHaveAttribute('href', '/goals/11/progress')
    expect(screen.getByRole('link', { name: 'Get a recommendation' })).toHaveAttribute('href', '/goals/12/recommend')
  })

  it('renders nothing without alerts', () => {
    const { container } = render(<PortfolioAlerts alerts={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('ProgressBar', () => {
  it('reports its value to screen readers and never overflows', () => {
    render(<ProgressBar percent={130} label="Car funded" />)
    const bar = screen.getByRole('progressbar', { name: 'Car funded' })
    expect(bar).toHaveAttribute('aria-valuenow', '130')
    expect((bar.firstElementChild as HTMLElement).style.width).toBe('100%')
  })
})
