import { useEffect, useId, useRef, type FormEvent, type ReactNode } from 'react'
export function FormModal({ open, title, children, busy, disabled, onClose, onSubmit }: { open: boolean; title: string; children: ReactNode; busy?: boolean; disabled?: boolean; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const dialog = useRef<HTMLDialogElement>(null); const titleId = useId()
  useEffect(() => { if (open && !dialog.current?.open) dialog.current?.showModal(); else if (!open && dialog.current?.open) dialog.current.close() }, [open])
  return <dialog ref={dialog} className="admin-modal" aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose() }}><form onSubmit={onSubmit}><header><p>RECORD EDITOR</p><h2 id={titleId}>{title}</h2><button type="button" aria-label="关闭" onClick={onClose}>×</button></header><div className="modal-fields">{children}</div><footer><button type="button" className="button button--quiet" onClick={onClose}>取消</button><button type="submit" className="button" disabled={busy || disabled}>{busy ? '正在保存…' : '保存记录'}</button></footer></form></dialog>
}
