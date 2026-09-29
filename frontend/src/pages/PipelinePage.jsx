import { Bot, Clock3, GitPullRequest, ShieldCheck, Sparkles } from "lucide-react";
import { stages } from "../data";
import { Heading, Metric, Panel, SectionTitle, Severity } from "../components/Primitives";

export default function PipelinePage({tickets,onNavigate}) {
 const metrics=[
  ["Active tickets","24","12%","vs last month",Bot,true],
  ["Median lead time","3h 42m","18%","target ≤ 6h",Clock3,true],
  ["Awaiting approval","03","1 critical","oldest 2h 04m",ShieldCheck,false],
  ["Deploy success","96.4%","2.1%","last 30 days",GitPullRequest,true],
 ];
 return <div className="page-wrap">
  <Heading eyebrow="Delivery control room · Tuesday, Sep 29" title="Pipeline overview" subtitle="A live view of ticket-to-deployment flow across agents and human gates." action={<button className="button primary" onClick={()=>onNavigate("approvals")}><ShieldCheck size={15}/>Review approvals</button>}/>
  <div className="metric-grid metric-4">{metrics.map(([label,value,change,note,Icon,good])=><Metric key={label} {...{label,value,change,note,icon:Icon,good}}/>)}</div>
  <div className="guardrail-banner"><span><ShieldCheck size={18}/></span><div><b>Policy gates are active</b><small>Critical severity, main merges, and production releases remain paused for human review.</small></div><strong>3 approvals waiting&nbsp; →</strong></div>
  <div className="board-head"><SectionTitle title="Ticket flow" detail="9 pipeline stages · horizontal scroll to inspect all columns"/><span className="board-live"><i/> Updated just now</span></div>
  <div className="kanban-scroll" tabIndex="0" role="region" aria-label="Nine-stage ticket pipeline"><div className="kanban-board">
   {stages.map((stage,index)=>{const rows=tickets.filter(t=>t.stage===stage);return <section className="kanban-column" key={stage} aria-label={`${stage}: ${rows.length} tickets`}><header><span className="stage-index">{String(index+1).padStart(2,"0")}</span><h3>{stage}</h3><b>{String(rows.length).padStart(2,"0")}</b></header><div className="column-divider"/><div className="ticket-list">
    {rows.map(ticket=><article className={`ticket ${ticket.waiting?"is-waiting":""}`} key={ticket.id}><div className="ticket-line"><small>{ticket.id}</small><Severity value={ticket.severity}/></div><h4>{ticket.title}</h4><span className="ticket-component">{ticket.component}</span><div className="ticket-meta"><span><Bot size={12}/>{ticket.agent}</span><span><Clock3 size={12}/>{ticket.age}</span></div>{ticket.waiting&&<div className="waiting"><ShieldCheck size={12}/>Waiting for human</div>}</article>)}
    {!rows.length&&<div className="column-empty">No tickets in this stage</div>}
   </div></section>})}
  </div></div>
  <div className="summary-grid"><Panel className="summary"><span className="summary-icon purple"><GitPullRequest size={17}/></span><div><small>CHANGE FLOW</small><b>7 changes in review</b><span>2 ready to merge after QA</span></div><a href="#approvals">Review queue ↗</a></Panel><Panel className="summary"><span className="summary-icon green"><Sparkles size={17}/></span><div><small>AGENT FLEET</small><b>11 agents · 3 mobile</b><span>All heartbeats received in the last 10s</span></div><a href="#agents">Fleet healthy <i className="online-dot"/></a></Panel></div>
 </div>;
}
