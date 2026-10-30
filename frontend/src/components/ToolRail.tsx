import { Check, CircleDashed, LoaderCircle, X } from 'lucide-react'
import type { ToolTrace } from '../api'

const labels:Record<string,string>={classify_car:'车型识别',query_car_info:'查询车型信息',generate_design_language:'生成设计语言',search_vehicle_views:'搜索多视角图像',build_design_board:'生成设计图板',save_vehicle_archive:'保存车型档案',search_archive_history:'检索历史档案'}

export default function ToolRail({trace}:{trace:ToolTrace[]}){
  return <aside className="tool-rail glass"><div className="rail-title">真实工具轨迹 <span>{trace.length} 次</span></div><div className="rail-line"/>{trace.length===0?<div className="tool-empty">等待智能体发起工具调用</div>:trace.map((item,i)=><details className={`tool ${item.status}`} key={`${item.call_id||item.tool}-${i}`} open={i===trace.length-1}><summary><div className="tool-dot">{item.status==='success'?<Check size={14}/>:item.status==='failed'?<X size={14}/>:<LoaderCircle size={14}/>}</div><div><strong>{labels[item.tool]||item.tool}</strong><code>{item.tool}</code></div><time>{item.duration_ms}ms</time></summary><div className="tool-detail"><span>参数</span><code>{JSON.stringify(item.arguments)}</code><span>结果</span><code>{JSON.stringify(item.result)}</code></div></details>)}</aside>
}
