import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { Button } from './Button'

export interface UploadProps {
  label?: string
  accept?: string
  multiple?: boolean
  onFiles: (files: File[]) => void
}

export function Upload({ label = '选择文件', accept, multiple = false, onFiles }: UploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const commit = (files: FileList | null) => { if (files?.length) onFiles(Array.from(files)) }
  const drop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); commit(event.dataTransfer.files) }
  const change = (event: ChangeEvent<HTMLInputElement>) => { commit(event.target.files); event.target.value = '' }
  return <div className={`upload ${dragging ? 'upload--dragging' : ''}`} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDragOver={(event) => event.preventDefault()} onDrop={drop}>
    <input ref={inputRef} className="sr-only" type="file" accept={accept} multiple={multiple} onChange={change} tabIndex={-1} />
    <div className="upload__mark" aria-hidden="true">↥</div>
    <strong>{label}</strong>
    <span>拖到这里，或从设备中选择</span>
    <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()}>浏览文件</Button>
  </div>
}
