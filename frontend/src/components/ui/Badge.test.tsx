import { render, screen } from '@testing-library/react'
import { Badge } from './Badge'
import { confidenceTone } from './confidence'

describe('confidence badges', () => {
  it.each([[90, 'success'], [89, 'warning'], [70, 'warning'], [69, 'caution'], [40, 'caution'], [39, 'danger']])('maps %i percent to %s', (score, tone) => {
    expect(confidenceTone(score as number)).toBe(tone)
  })
  it('renders an accessible text label', () => {
    render(<Badge tone={confidenceTone(96)}>置信度 96%</Badge>)
    expect(screen.getByText('置信度 96%')).toHaveClass('badge--success')
  })
})
