import { forwardRef, useId, type InputHTMLAttributes } from 'react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, id: providedId, className = '', ...props }, ref,
) {
  const generatedId = useId()
  const id = providedId ?? generatedId
  const descriptionId = `${id}-description`
  return <div className={`field ${className}`}>
    <label className="field__label" htmlFor={id}>{label}</label>
    <input ref={ref} id={id} className="field__control" aria-invalid={Boolean(error)} aria-describedby={(hint || error) ? descriptionId : undefined} {...props} />
    {(error || hint) && <span id={descriptionId} role={error ? 'alert' : undefined} className={error ? 'field__error' : 'field__hint'}>{error || hint}</span>}
  </div>
})
