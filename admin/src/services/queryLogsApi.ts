import { api } from './apiClient'
import type { QueryCorrection, QueryLogDetail, QueryLogPage, QueryLogStats } from '../types/queryLogs'

export interface QueryLogQuery { q?:string;source?:string;status?:string;date_from?:string;date_to?:string;page:number;page_size:number }
const query=(values:QueryLogQuery)=>{const params=new URLSearchParams();Object.entries(values).forEach(([key,value])=>{if(value!==undefined&&value!=='')params.set(key,String(value))});return params.toString()}
export const listQueryLogs=(values:QueryLogQuery,signal?:AbortSignal)=>api.get<QueryLogPage>(`/api/v1/admin/query-logs?${query(values)}`,{signal})
export const getQueryLogStats=()=>api.get<QueryLogStats>('/api/v1/admin/query-logs/stats')
export const getQueryLog=(id:string)=>api.get<QueryLogDetail>(`/api/v1/admin/query-logs/${id}`)
export const correctQueryLog=(id:string,payload:{recommended_part_id:string|null;correct_part_id:string;reason:string})=>api.post<QueryCorrection>(`/api/v1/admin/query-logs/${id}/corrections`,payload)
