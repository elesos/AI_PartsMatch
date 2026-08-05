import { useEffect, useId, useRef } from 'react'
export function ConfirmDialog({ open, title, description, busy, onCancel, onConfirm }: { open: boolean; title: string; description: string; busy?: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null); const titleId = useId(); const descriptionId = useId()
  useEffect(() => { if (open && !dialog.current?.open) dialog.current?.showModal(); else if (!open && dialog.current?.open) dialog.current.close() }, [open])
  return <dialog ref={dialog} className="admin-modal confirm-dialog" aria-labelledby={titleId} aria-describedby={descriptionId} onCancel={event => { event.preventDefault(); onCancel() }}><div><header><p>DESTRUCTIVE ACTION</p><h2 id={titleId}>{title}</h2></header><p id={descriptionId}>{description}</p><footer><button type="button" className="button button--quiet" onClick={onCancel}>取消</button><button type="button" className="button button--danger" disabled={busy} onClick={onConfirm}>{busy ? '正在处理…' : '确认删除'}</button></footer></div></dialog>
}
