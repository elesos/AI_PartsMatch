import type { HTMLAttributes, ReactNode } from 'react'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  title?: string
  meta?: ReactNode
}

export function Card({ title, meta, className = '', children, ...props }: CardProps) {
  return <section className={`card ${className}`} {...props}>
    {(title || meta) && <header className="card__header">
      {title && <h2 className="card__title">{title}</h2>}
      {meta && <div className="card__meta">{meta}</div>}
    </header>}
    <div className="card__body">{children}</div>
  </section>
}
