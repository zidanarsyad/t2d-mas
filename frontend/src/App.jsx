import { lazy,Suspense,useCallback,useEffect,useState } from "react";
import { Activity,AlertTriangle,ArrowUpRight,Bell,Bot,CircleHelp,Command,FileClock,Gauge,GitBranch,LayoutDashboard,Moon,Search,ShieldCheck,Smartphone,Sun,Workflow,X } from "lucide-react";
import { seedTickets } from "./data";
import { useLiveEvents } from "./hooks/useLiveEvents";
const PipelinePage=lazy(()=>import("./pages/PipelinePage.jsx"));
const AgentsPage=lazy(()=>import("./pages/AgentsPage.jsx"));
const TracePage=lazy(()=>import("./pages/TracePage.jsx"));
const ApprovalsPage=lazy(()=>import("./pages/ApprovalsPage.jsx"));
const PerformancePage=lazy(()=>import("./pages/PerformancePage.jsx"));
const nav=[
 {id:"pipeline",label:"Pipeline Overview",icon:LayoutDashboard},
 {id:"agents",label:"Agent Status",icon:Bot},
 {id:"trace",label:"Decision Trace",icon:FileClock},
 {id:"approvals",label:"Approval Inbox",icon:ShieldCheck,count:3},
 {id:"performance",label:"Performance Report",icon:Gauge},
];
const title={pipeline:"Overview",agents:"Agent fleet",trace:"Decision trace",approvals:"Approval inbox",performance:"Performance"};
export default function App(){
 const [page,setPage]=useState("pipeline"),[theme,setTheme]=useState(()=>localStorage.getItem("t2d-theme")||"light"),[fontSize,setFontSize]=useState(()=>["standard","large","larger"].includes(localStorage.getItem("t2d-font-size"))?localStorage.getItem("t2d-font-size"):"standard"),[tickets,setTickets]=useState(seedTickets),[search,setSearch]=useState(false),[help,setHelp]=useState(false),[query,setQuery]=useState("");
 const onEvent=useCallback(event=>{
  if(event.type==="pipeline.advanced")setTickets(rows=>rows.map(t=>t.id===event.ticket_id?{...t,stage:capitalize(event.stage),waiting:false}:t));
  if(event.type==="approval.resolved"&&event.approved)setTickets(rows=>rows.map(t=>t.id===event.ticket_id?{...t,waiting:false}:t));
 },[]);
 const {connected,lastUpdate}=useLiveEvents(onEvent);
 useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem("t2d-theme",theme)},[theme]);
 useEffect(()=>{document.documentElement.dataset.fontSize=fontSize;localStorage.setItem("t2d-font-size",fontSize)},[fontSize]);
 useEffect(()=>{const key=e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();setSearch(v=>!v)}if(e.key==="Escape"){setSearch(false);setHelp(false)}};window.addEventListener("keydown",key);return()=>window.removeEventListener("keydown",key)},[]);
 const matches=query.trim()?tickets.filter(t=>`${t.id} ${t.title} ${t.component}`.toLowerCase().includes(query.toLowerCase())):tickets;
 const go=id=>{setPage(id);setSearch(false)};
 return <div className="app-shell min-h-screen bg-[var(--bg)] text-[var(--ink)]">
  <aside className="sidebar flex flex-col"><div className="brand flex items-center gap-2"><span><Workflow size={18}/></span><b>T2D<i>·</i>MAS<small>delivery control</small></b></div><small className="nav-caption">WORKSPACE</small><nav aria-label="Main navigation" className="navigation grid gap-1">{nav.map(({id,label,icon:Icon,count})=><button key={id} onClick={()=>go(id)} className={`nav-link flex items-center gap-2 ${page===id?"active":""}`} aria-current={page===id?"page":undefined}><Icon size={17}/><span>{label}</span>{count&&<b>{count}</b>}</button>)}</nav><hr/><small className="nav-caption">OPERATIONS</small><button className="nav-link disabled" disabled><GitBranch size={17}/><span>Integrations</span><small>Soon</small></button><button className="nav-link disabled" disabled><Activity size={17}/><span>System health</span><small>Soon</small></button><div className="sidebar-bottom"><div className="guardrail-mini"><ShieldCheck size={15}/><span><b>Guardrails active</b><small>Human approval required</small></span><i/></div><button className="nav-link help" onClick={()=>setHelp(true)}><CircleHelp size={16}/><span>Help & documentation</span><ArrowUpRight size={13}/></button></div><div className="profile"><i>Z</i><span><b>Zidar</b><small>Project owner</small></span></div></aside>
  <main className="main-area"><header className="topbar flex items-center justify-between"><div className="crumb"><span>ACE Project</span><i>/</i><b>{title[page]}</b></div><div className="top-actions flex items-center gap-2"><button className="search-trigger" onClick={()=>setSearch(true)} aria-label="Search tickets"><Search size={15}/><span>Search tickets…</span><kbd><Command size={10}/> K</kbd></button><span className={`connection ${connected?"connected":""}`} title={lastUpdate?`Updated ${lastUpdate.toLocaleTimeString()}`:"FastAPI SSE connection status"}><i/>{connected?"Live · SSE":"Demo mode"}</span><button className="icon-btn notification" onClick={()=>go("approvals")} aria-label="Open approval notifications"><Bell size={16}/><i/></button><label className="font-size-control"><span aria-hidden="true">Aa</span><select aria-label="Font size" value={fontSize} onChange={event=>setFontSize(event.target.value)}><option value="standard">Standard</option><option value="large">Large</option><option value="larger">Extra large</option></select></label><button className="theme-button" onClick={()=>setTheme(theme==="light"?"dark":"light")} aria-label={`Switch to ${theme==="light"?"dark":"light"} mode`}>{theme==="light"?<Moon size={15}/>:<Sun size={15}/>}</button><span className="top-avatar">Z</span></div></header>
   <div className="page-content w-full flex-1"><Suspense fallback={<div className="page-loading" role="status">Loading dashboard view…</div>}>{page==="pipeline"&&<PipelinePage tickets={matches} onNavigate={go}/>}{page==="agents"&&<AgentsPage/>}{page==="trace"&&<TracePage/>}{page==="approvals"&&<ApprovalsPage onNavigate={go}/>}{page==="performance"&&<PerformancePage/>}</Suspense></div>
   <footer className="app-footer"><span><i/>T2D-MAS prototype · Policy v1.2</span><span>Times shown in Asia/Jakarta (WIB)</span></footer>
  </main>
  {search&&<div className="overlay" onMouseDown={e=>e.target===e.currentTarget&&setSearch(false)}><section className="search-modal" role="dialog" aria-modal="true" aria-label="Search tickets"><div className="search-input"><Search size={17}/><input autoFocus placeholder="Search ticket ID, title, or component…" value={query} onChange={e=>setQuery(e.target.value)}/><button onClick={()=>setSearch(false)} aria-label="Close search"><X size={15}/></button></div><small className="search-label">{query?`${matches.length} MATCHING TICKETS`:"RECENT TICKETS"}</small><div className="search-results">{(query?matches:tickets.slice(0,5)).map(t=><button key={t.id} onClick={()=>go("pipeline")}><AlertTriangle size={14}/><span><b>{t.id}</b><small>{t.title}</small></span><em className={`sev-text-${t.severity.toLowerCase()}`}>{t.severity}</em></button>)}</div><p>Search by ticket ID, title, or component.</p></section></div>}
  {help&&<div className="overlay" onMouseDown={e=>e.target===e.currentTarget&&setHelp(false)}><section className="search-modal help-modal" role="dialog" aria-modal="true" aria-label="Help and documentation"><div className="search-input"><CircleHelp size={17}/><b>Help & documentation</b><button onClick={()=>setHelp(false)} aria-label="Close help"><X size={15}/></button></div><div className="help-content"><p>Explore the dashboard or open the local backend references.</p><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Open API documentation <ArrowUpRight size={13}/></a><a href="http://localhost:8000/health" target="_blank" rel="noreferrer">Check backend health <ArrowUpRight size={13}/></a><small>Tip: use the Font size menu in the header to adjust readability. Press Ctrl+K to search tickets.</small></div></section></div>}
 </div>
}
function capitalize(value=""){return value?value[0].toUpperCase()+value.slice(1):value}
