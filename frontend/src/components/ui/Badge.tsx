import type { HTMLAttributes } from 'react'

type Tone = 'neutral' | 'success' | 'warning' | 'caution' | 'danger'
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> { tone?: Tone }

export function Badge({ tone = 'neutral', className = '', children, ...props }: BadgeProps) {
  return <span className={`badge badge--${tone} ${className}`} {...props}>{children}</span>
}
