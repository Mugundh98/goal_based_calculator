import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MarkdownText } from './MarkdownText'

describe('MarkdownText', () => {
  it('renders headings, emphasis, lists and code', () => {
    const { container } = render(
      <MarkdownText text={'### Your plan\nYou need **₹22,224** a month, *starting now*.\n\n* First\n* Second\n\n1. One\n2. Two\n\nUse `XIRR`.'} />,
    )
    expect(screen.getByText('Your plan')).toBeInTheDocument()
    expect(screen.getByText('₹22,224').tagName).toBe('STRONG')
    expect(screen.getByText('starting now').tagName).toBe('EM')
    expect(container.querySelectorAll('ul > li')).toHaveLength(2)
    expect(container.querySelectorAll('ol > li')).toHaveLength(2)
    expect(screen.getByText('XIRR').tagName).toBe('CODE')
  })

  it('renders a Markdown table', () => {
    render(<MarkdownText text={'| Fund | Return |\n|---|---:|\n| HDFC Mid Cap | 15.5% |\n| Nippon Large Cap | 11.4% |'} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Fund', 'Return'])
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })

  it('never turns model output into HTML (no script injection)', () => {
    const { container } = render(<MarkdownText text={'<script>alert(1)</script> <img src=x onerror="alert(2)"> **bold**'} />)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<script>alert(1)</script>')
  })
})
