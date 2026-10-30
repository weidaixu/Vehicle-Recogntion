import { ChangeEvent, useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, Archive, ArrowRight, Box, Check, Download, Gauge, Image as ImageIcon, Menu, MessageCircle, ScanLine, Search, Target, Upload } from 'lucide-react'
import DepthBackground from './components/DepthBackground'
import ToolRail from './components/ToolRail'
import { api, ApiError, AgentResponse, ArchiveRecord, Classification, DesignLanguage, Status, ToolTrace, VehicleView } from './api'

type ChatMessage = { role:'user'|'assistant'; content:string }

const newSession = () => typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`

export default function App(){
  const [sessionId] = useState(newSession)
  const [status,setStatus]=useState<Status|null>(null)
  const [file,setFile]=useState<File|null>(null)
  const [preview,setPreview]=useState('')
  const [task,setTask]=useState('')
  const [messages,setMessages]=useState<ChatMessage[]>([])
  const [trace,setTrace]=useState<ToolTrace[]>([])
  const [result,setResult]=useState<Classification|null>(null)
  const [design,setDesign]=useState<DesignLanguage|null>(null)
  const [views,setViews]=useState<VehicleView[]>([])
  const [board,setBoard]=useState<string|null>(null)
  const [archives,setArchives]=useState<ArchiveRecord[]>([])
  const [historyOpen,setHistoryOpen]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [dragging,setDragging]=useState(false)

  useEffect(()=>{api.status().then(setStatus).catch(()=>setStatus(null))},[])
  useEffect(()=>()=>{if(preview) URL.revokeObjectURL(preview)},[preview])

  const choose=(next:File|null)=>{
    if(busy)return
    if(!next)return
    if(!next.type.startsWith('image/')){setError('请选择 JPG、PNG 等图片文件');return}
    if(next.size>15*1024*1024){setError('图片不能超过 15 MB');return}
    if(preview)URL.revokeObjectURL(preview)
    setFile(next);setPreview(URL.createObjectURL(next));setError('')
  }
  const onInput=(event:ChangeEvent<HTMLInputElement>)=>choose(event.target.files?.[0]||null)
  const submit=async()=>{
    if(busy)return
    if(!file&&!task.trim()){setError('请上传车辆照片或输入任务');return}
    const message=task.trim()||'请识别这辆车，并建立设计研究档案'
    setBusy(true);setError('')
    try{
      const response:AgentResponse=file?await api.agentUpload(file,sessionId,message):await api.agentMessage(sessionId,message)
      setMessages(prev=>[...prev,{role:'user',content:message},{role:'assistant',content:response.answer}])
      setTrace(response.trace);setResult(response.classification);setDesign(response.design_language);setViews(response.views);setBoard(response.board_url);setTask('');setFile(null)
    }catch(caught){setError(caught instanceof ApiError?caught.message:'智能体暂时不可用，请检查后端与 DeepSeek 配置')}
    finally{setBusy(false)}
  }
  const loadHistory=async()=>{setHistoryOpen(true);try{setArchives((await api.archives()).items)}catch(caught){setError(caught instanceof ApiError?caught.message:'历史档案暂时不可用')}}
  const confidence=useMemo(()=>result?`${(result.confidence*100).toFixed(1)}%`:'—',[result])
  const isRejected=Boolean(result?.label==='unknown'||result?.rejected)

  return <main className={`app ${busy?'is-working':''}`}>
    <img className="photo-bg" src="/assets/showroom-original.jpg" data-rotation="left-90" alt="DriveScope visual background"/><DepthBackground active={busy}/><div className="shade"/><div className="speed-lines"/>
    <header><a className="brand" href="#top">DriveScope</a><span className="brand-manifesto">CAPTURE · UNDERSTAND · ARCHIVE</span><div className="header-actions"><div className="system"><span className={status?.model_ready?'online':''}/>{status?.model_ready?'VISION ONLINE':'CONNECTING'}</div><button className="menu-button" aria-label="页面菜单"><Menu size={22}/></button></div></header>
    <section id="top" className="hero agent-hero">
      <div className="hero-copy"><span className="section-no">CAR SHOW / VISUAL RESEARCH AGENT</span><h1>看见一辆车，读懂它的设计。</h1><p>自训练视觉模型识别车型，DeepSeek 调用工具查询资料、整理设计解读并保存档案。设计解读基于车型资料，不代表对上传照片细节的直接观察。</p></div>
      <aside className="proof-rail" aria-label="系统能力"><div><strong>{status?.class_count||'—'}</strong><span>车型识别类别</span></div><div><strong>{status?`${(status.macro_f1*100).toFixed(1)}%`:'—'}</strong><span>验证集 Macro-F1</span></div><div><strong>4</strong><span>核心分析维度</span></div><p>A DEEPER WAY<br/>TO SEE CARS.</p></aside>
      <section className="agent-workspace glass" data-layout="dialogue-with-tools">
        <div className="workspace-main">
          <div className="workspace-kicker"><MessageCircle size={16}/> 连续会话 <code>01 / 04 · {sessionId.slice(0,8)}</code></div>
          <div className="workspace-intro"><strong>上传一张车展照片，<br/>让 AI 帮你读懂这辆车的设计。</strong><span>从外观到设计语言，从细节到品牌基因，获得专业、深入、可视化的分析结果。</span></div>
          <div className="capability-strip" aria-label="分析流程"><div><ScanLine/><span><b>车型识别</b><small>Vehicle Detection</small></span><Check/></div><div><Box/><span><b>设计语言解析</b><small>Design Language</small></span><Check/></div><div><Activity/><span><b>细分市场分析</b><small>Segment Analysis</small></span><Check/></div><div><Target/><span><b>生成分析报告</b><small>Report Generation</small></span><Check/></div></div>
          <div className="conversation" aria-live="polite">
            {messages.length===0?<div className="conversation-empty">等待你的第一张车辆照片。<small>上传后可继续用自然语言追问设计细节。</small></div>:messages.map((message,index)=><div className={`bubble ${message.role}`} key={`${message.role}-${index}`}><span>{message.role==='user'?'YOU':'DRIVESCOPE'}</span><p>{message.content}</p></div>)}
          </div>
          <div className="composer">
            <div className={`dropzone ${dragging?'is-dragging':''}`} onDragEnter={event=>{event.preventDefault();setDragging(true)}} onDragOver={event=>{event.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={event=>{event.preventDefault();setDragging(false);choose(event.dataTransfer.files?.[0]||null)}}>
              {preview?<img src={preview} alt="待分析的车辆照片"/>:<Upload size={18}/>}<label htmlFor="vehicle-upload">{file?file.name:'上传车辆照片'}</label><input id="vehicle-upload" aria-label="上传车辆照片" type="file" accept="image/*" onChange={onInput}/>
            </div>
            <label className="sr-only" htmlFor="agent-task">给智能体的任务</label><textarea id="agent-task" aria-label="给智能体的任务" value={task} onChange={event=>setTask(event.target.value)} onKeyDown={event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter')void submit()}} placeholder="给智能体一个任务，支持连续追问…"/>
            <button className="primary magnetic" aria-label={file?'执行任务':'发送追问'} onClick={()=>void submit()} disabled={busy}>{busy?'工具运行中…':file?'执行任务':'发送追问'}<ArrowRight size={17}/></button>
          </div>
          {error&&<div className="error agent-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
        </div>
        <ToolRail trace={trace}/>
      </section>
      <div className="scene-note">CARS<br/>CONNECT PEOPLE<br/>TO A BRIGHTER TOMORROW.</div>
    </section>

    <section className="results glass">
      <div className="result-head"><div><span className="section-no">SESSION RESULT / 真实上下文</span><h2>{result?.name?.replaceAll('_',' ')||'第一张车展照片的分析结果'}</h2></div><div className="confidence"><Gauge/><span>识别置信度</span><strong>{confidence}</strong></div></div>
      <div className="insight-grid">
        <article className="insight-card"><ImageIcon/><div><span>车型识别 <small>VEHICLE IDENTIFICATION</small></span><strong>{result?.name?.replaceAll('_',' ')||'等待识别'}</strong><p>{result?`类别 ${result.label} · 置信度 ${confidence}`:'上传车辆照片后显示车型与置信度。'}</p></div></article>
        <article className="insight-card"><Box/><div><span>设计关键词 <small>DESIGN KEYWORDS</small></span><strong>{design?.summary||'等待设计语言分析'}</strong><p>{design?.surface_language||'曲面、比例与灯组特征将在这里汇总。'}</p></div></article>
        <article className="insight-card"><Activity/><div><span>空气动力学 <small>AERODYNAMIC ANALYSIS</small></span><strong>{design?'设计效能研判':'等待分析'}</strong><p>{design?.aerodynamics||'智能体完成设计语言工具后显示空气动力学结论。'}</p></div></article>
        <article className="insight-card"><Target/><div><span>品牌定位 <small>BRAND POSITIONING</small></span><strong>{result?result.name.split('_')[0]:'等待车型上下文'}</strong><p>{design?.brand_cues||'结合车型与设计特征解释品牌视觉基因。'}</p></div></article>
      </div>
      {isRejected&&<div className="error"><AlertTriangle size={17}/>未识别为本组支持的车型；系统已停止后续车型工具，请换用车身完整、光线清晰的照片。</div>}
      {!result?<div className="empty">完成第一轮工具调用后，这里会展开车型、设计语言与多视角档案。</div>:<>
        <div className="result-grid"><div className="ranking"><h3>识别候选</h3>{result.top_k.map((item,index)=><div className="rank" key={item.label}><span>0{index+1}</span><b>{item.name.replaceAll('_',' ')}</b><i style={{'--score':`${item.confidence*100}%`} as React.CSSProperties}>{(item.confidence*100).toFixed(1)}%</i></div>)}</div>
        <div className="analysis"><h3>设计语言</h3>{design?<><p className="summary">{design.summary}</p><dl><div><dt>车身比例</dt><dd>{design.proportions}</dd></div><div><dt>灯组特征</dt><dd>{design.lighting_signature}</dd></div><div><dt>曲面语言</dt><dd>{design.surface_language}</dd></div><div><dt>局限</dt><dd>{design.limitations}</dd></div></dl></>:<p className="empty small">等待智能体调用设计语言工具。</p>}</div></div>
        <div className="archive"><div className="archive-head"><h3><ImageIcon size={18}/> 多视角视觉档案</h3><span>{views.length} 张 · 资料来源随工具结果保存</span></div>{views.length?<div className="filmstrip">{views.map((view,index)=><figure key={`${view.url}-${index}`}><img src={view.thumbnail_url} alt={`${result.name} ${view.view_hint}`}/><figcaption>{view.source_kind==='wikimedia'?'Wikimedia Commons':'课程数据集'} · {view.license_name}</figcaption></figure>)}</div>:<p className="archive-empty">智能体尚未返回视觉素材，或网络检索失败后没有本地图像。</p>}{board&&<a className="export" href={board} target="_blank" rel="noreferrer"><Download size={18}/><span>查看设计图板<small>图像与来源清单已由后端生成</small></span><ArrowRight/></a>}</div>
      </>}
      <div className="history-bar"><button className="history-button" onClick={()=>void loadHistory()}><Archive size={16}/>查看历史档案</button><span>Session 会保存图片引用、识别结果、设计分析、视觉档案与图板结果。</span></div>
      {historyOpen&&<div className="history-panel"><div className="history-title"><h3><Search size={16}/> 已保存的车型档案</h3><button onClick={()=>setHistoryOpen(false)}>收起</button></div>{archives.length?archives.map(item=><div className="history-item" key={item.archive_id}><strong>{item.title}</strong><span>{item.class_id} · {new Date(item.created_at).toLocaleString()}</span></div>):<p className="archive-empty">还没有保存的档案。</p>}</div>}
    </section>
    <footer><span>DriveScope — CAPTURE · UNDERSTAND · ARCHIVE</span><span>SESSION {sessionId.slice(0,8)}</span></footer>
  </main>
}
