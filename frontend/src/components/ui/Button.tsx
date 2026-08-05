import { forwardRef, type ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', loading = false, className = '', disabled, children, ...props }, ref,
) {
  return <button ref={ref} className={`button button--${variant} ${className}`} disabled={disabled || loading} aria-busy={loading} {...props}>
    {loading && <span className="button__spinner" aria-hidden="true" />}
    {children}
  </button>
})
