import React,{useEffect,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {LineChart,Line,XAxis,YAxis,Tooltip,Legend,ResponsiveContainer} from 'recharts'
import './index.css'

const API=import.meta.env.VITE_API_URL||'http://localhost:8000'
const WS=(API.replace('http','ws'))+'/ws/metrics'

function App(){
 const [m,setM]=useState(null),[hist,setHist]=useState([]),[status,setStatus]=useState(null)
 useEffect(()=>{fetch(API+'/metrics/history').then(r=>r.json()).then(x=>setHist(x));fetch(API+'/rate-limit/status').then(r=>r.json()).then(setStatus)
   const ws=new WebSocket(WS);ws.onmessage=e=>{const x=JSON.parse(e.data);setM(x);setHist(h=>[...h.slice(-59),x])};return()=>ws.close()},[])
 useEffect(()=>{if(m) setStatus(s=>({...s,...m}))},[m])
 const v=m||status||{}
 const cards=[['Requests/s',v.requests_per_sec??0],['Total Requests',v.total_requests??0],['Allowed',v.accepted_requests??0],['Rejected',v.rejected_requests??0],['Current Limit',v.current_rate_limit??0],['Avg Latency',`${v.avg_latency_ms??0} ms`],['CPU',`${v.cpu_utilization??0}%`],['Memory',`${v.memory_utilization??0}%`]]
 return <div className="p-8 max-w-[1500px] mx-auto">
   <header className="flex justify-between items-end mb-7"><div><div className="text-3xl font-bold">RateGuard</div><div className="text-zinc-400 mt-1">Adaptive API Gateway & Dynamic Rate Limiting Engine</div></div>
   <div className="card py-3 px-5"><span className="text-zinc-400">State</span> <b className="ml-3">{v.system_state||'CONNECTING'}</b></div></header>
   <div className="grid grid-cols-4 gap-4 mb-5">{cards.map(([k,x])=><div className="card" key={k}><div className="text-zinc-400 text-sm">{k}</div><div className="text-2xl font-semibold mt-2">{x}</div></div>)}</div>
   <div className="grid grid-cols-2 gap-5">
    <Chart title="Requests / sec" data={hist} keys={['requests_per_sec']}/>
    <Chart title="Accepted vs Rejected" data={hist} keys={['accepted_requests','rejected_requests']}/>
    <Chart title="CPU / Memory" data={hist} keys={['cpu_utilization','memory_utilization']}/>
    <Chart title="Latency / Dynamic Limit" data={hist} keys={['avg_latency_ms','current_rate_limit']}/>
   </div>
   <div className="card mt-5 grid grid-cols-4 gap-6">
    <div><span className="text-zinc-400">Algorithm</span><div className="font-semibold mt-1">{v.algorithm||'TOKEN_BUCKET'}</div></div>
    <div><span className="text-zinc-400">System State</span><div className="font-semibold mt-1">{v.system_state||'NORMAL'}</div></div>
    <div><span className="text-zinc-400">Current Limit</span><div className="font-semibold mt-1">{v.current_rate_limit||0} req/s</div></div>
    <div><span className="text-zinc-400">Bucket Utilization</span><div className="font-semibold mt-1">{v.bucket_utilization||0}%</div></div>
   </div>
 </div>
}
function Chart({title,data,keys}){return <div className="card"><div className="font-semibold mb-4">{title}</div><div style={{height:270}}><ResponsiveContainer><LineChart data={data}><XAxis dataKey="timestamp" tickFormatter={x=>new Date(x*1000).toLocaleTimeString()}/><YAxis/><Tooltip labelFormatter={x=>new Date(x*1000).toLocaleTimeString()}/><Legend/>{keys.map(k=><Line key={k} type="monotone" dataKey={k} dot={false}/>)}</LineChart></ResponsiveContainer></div></div>}
createRoot(document.getElementById('root')).render(<App/>)
