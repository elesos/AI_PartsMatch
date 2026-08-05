import { useEffect, useRef, type ReactNode } from 'react'
import { Button } from './Button'
import { useTranslation } from 'react-i18next'

export interface ModalProps {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
}

export function Modal({ open, title, children, onClose, footer }: ModalProps) {
  const { t } = useTranslation()
  const panelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panelRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    document.body.classList.add('modal-open')
    return () => { document.removeEventListener('keydown', onKeyDown); document.body.classList.remove('modal-open'); previous?.focus() }
  }, [open, onClose])
  if (!open) return null
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div ref={panelRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1}>
      <header className="modal__header"><h2 id="modal-title">{title}</h2><Button variant="ghost" onClick={onClose} aria-label={t('common.close')}>×</Button></header>
      <div className="modal__body">{children}</div>
      {footer && <footer className="modal__footer">{footer}</footer>}
    </div>
  </div>
}
