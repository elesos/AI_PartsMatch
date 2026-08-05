import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { listCrossReferences } from '../services/crossReferencesApi'
import type { CrossReference } from '../types/crossReferences'

export function CrossReferencePanel({ partId, partNo, writable }: { partId:string;partNo:string;writable:boolean }) {
  const [host,setHost]=useState<Element|null>(null); const [rows,setRows]=useState<CrossReference[]>([]); const [error,setError]=useState('')
  useEffect(()=>{const timer=window.setTimeout(()=>setHost(document.querySelector('.part-detail-panel')),0);return()=>window.clearTimeout(timer)},[partId])
  useEffect(()=>{const controller=new AbortController();void listCrossReferences({part_id:partId,direction:'all',page:1,page_size:100,sort_by:'priority',sort_dir:'desc'},controller.signal).then(page=>{setRows(page.items);setError('')}).catch(reason=>{if(!(reason instanceof DOMException&&reason.name==='AbortError'))setError(reason instanceof Error?reason.message:'读取失败')});return()=>controller.abort()},[partId])
  if(!host)return null
  const content=<section className="detail-section crossref-perspective"><div className="section-title"><div><p className="eyebrow">DIRECTED RELATIONS</p><h3>替代件关系</h3></div><Link className="button button--quiet" to={`/cross-refs?part_id=${partId}&direction=all`}>{writable?'管理全部':'查看全部'}</Link></div>{error?<p className="panel-error">{error}</p>:!rows.length?<p className="detail-empty">{partNo} 暂无替代关系。</p>:<div className="perspective-groups"><div><h4>作为原件 / SOURCE</h4>{rows.filter(row=>row.source_part_id===partId).map(row=><Link key={row.id} to={`/cross-refs?part_id=${partId}&direction=source`}><b>{partNo}</b><i>→</i><strong>{row.target_part.part_no}</strong><small>{row.target_part.brand} · {row.relation_type}</small></Link>)}{!rows.some(row=>row.source_part_id===partId)&&<span>无</span>}</div><div><h4>作为替代件 / TARGET</h4>{rows.filter(row=>row.target_part_id===partId).map(row=><Link key={row.id} to={`/cross-refs?part_id=${partId}&direction=target`}><b>{row.source_part.part_no}</b><i>→</i><strong>{partNo}</strong><small>{row.source_part.brand} · {row.relation_type}</small></Link>)}{!rows.some(row=>row.target_part_id===partId)&&<span>无</span>}</div></div>}</section>
  return createPortal(content,host)
}
