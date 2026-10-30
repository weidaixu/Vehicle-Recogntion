export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError' }
}

export async function requestJson<T>(url: string, init: RequestInit = {}, fetcher: typeof fetch = fetch): Promise<T> {
  const response = await fetcher(url, init)
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try { message = (await response.json()).detail || message } catch { /* non-json response */ }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export type Status = { model_ready: boolean; class_count: number; macro_f1: number; deepseek_configured: boolean; webgl_assets_ready: boolean }
export type Classification = { label: string; name: string; confidence: number; rejected: boolean; top_k: Array<{label:string; name:string; confidence:number}>; trace_id?:string }
export type DesignLanguage = { summary:string; proportions:string; lighting_signature:string; surface_language:string; aerodynamics:string; brand_cues:string; limitations:string; trace_id:string }
export type VehicleView = { url:string; thumbnail_url:string; source_kind:string; view_hint:string; author:string; license_name:string; license_url:string; source_page:string; modified:boolean }

export type ToolTrace = { tool:string; status:string; arguments:Record<string, unknown>; result:Record<string, unknown>; duration_ms:number; call_id?:string|null }
export type AgentResponse = { session_id:string; answer:string; classification:Classification|null; design_language:DesignLanguage|null; views:VehicleView[]; board_url:string|null; trace:ToolTrace[]; messages?:Array<{role:string;content:string;image_ref?:string|null}> }
export type ArchiveRecord = { archive_id:string; session_id:string; class_id:string; title:string; image_ref?:string|null; design_language?:Record<string, unknown>; views?:VehicleView[]; board_url?:string|null; created_at:string }

export const api = {
  status: () => requestJson<Status>('/api/status'),
  classify: (file: File, threshold?: number) => { const body = new FormData(); body.append('image', file); if (threshold !== undefined) body.append('threshold', String(threshold)); return requestJson<Classification>('/api/classify', { method:'POST', body }) },
  agentUpload: (file: File, sessionId: string, message = '') => { const body = new FormData(); body.append('image', file); body.append('session_id', sessionId); body.append('message', message || '请分析这辆车的设计语言并建立视觉档案'); return requestJson<AgentResponse>('/api/agent/upload', {method:'POST', body}) },
  agentMessage: (sessionId:string, message:string) => requestJson<AgentResponse>('/api/agent', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId,message})}),
  session: (sessionId:string) => requestJson<{session_id:string;image_ref:string|null;classification:Classification|null;design_language:DesignLanguage|null;views:VehicleView[];board_url:string|null;messages:Array<{role:string;content:string}>;tool_runs:ToolTrace[]}>(`/api/session/${sessionId}`),
  archives: (query = '') => requestJson<{items:ArchiveRecord[]}>(`/api/archives?q=${encodeURIComponent(query)}`),
  design: (classId: string, focus = '') => requestJson<DesignLanguage>('/api/design-language', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:crypto.randomUUID(), class_id:classId, user_focus:focus}) }),
  views: (classId: string) => requestJson<{items:VehicleView[]; trace_id:string; offline_fallback:boolean}>(`/api/vehicle-views/${classId}?network=true&limit=12`),
  board: (classId:string, designLanguage:DesignLanguage, imagePaths:string[]) => requestJson<{board_url:string;manifest_url:string;trace_id:string}>('/api/design-board', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_id:classId,design_language:designLanguage,image_paths:imagePaths})}),
}
