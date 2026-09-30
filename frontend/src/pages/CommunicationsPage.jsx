import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowDown, ArrowRight, Bot, Check, CheckCheck, CircleDot, Clock3, GitBranch, Maximize2, MessageSquareText, Pause, Play, Plus, Radio, RotateCcw, ShieldCheck, Sparkles, Users, ZoomIn, ZoomOut } from "lucide-react";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";

const replayMessages = [
  { time:"21:35:11.021", sender:"Broker-Assign", receivers:["Worker-Plan","Worker-Investigate","Worker-Impl"], performative:"cfp", summary:"Request bids for checkout incident investigation", content:{ticket_id:"TCK-1042", task:"Rank likely root causes for the checkout crash", deadline_s:2}, policy:{tau:0.70,risk_max:0.60}, status:"broadcast" },
  { time:"21:35:11.183", sender:"Worker-Plan", receivers:["Broker-Assign"], performative:"propose", summary:"Bid submitted · utility 0.63", content:{worker_id:"Worker-Plan",skill:0.71,load:0.48,cost:0.31,utility:0.63}, status:"proposal" },
  { time:"21:35:11.246", sender:"Worker-Investigate", receivers:["Broker-Assign"], performative:"propose", summary:"Bid submitted · utility 0.69", content:{worker_id:"Worker-Investigate",skill:0.84,load:0.26,cost:0.29,utility:0.69}, status:"proposal" },
  { time:"21:35:11.302", sender:"Worker-Impl", receivers:["Broker-Assign"], performative:"propose", summary:"Bid submitted · utility 0.66", content:{worker_id:"Worker-Impl",skill:0.79,load:0.31,cost:0.38,utility:0.66}, status:"proposal" },
  { time:"21:35:11.407", sender:"Broker-Assign", receivers:["Worker-Investigate"], performative:"accept-proposal", summary:"Worker-Investigate selected · highest utility 0.69", content:{worker_id:"Worker-Investigate",utility:0.69}, status:"selected" },
  { time:"21:35:11.411", sender:"Broker-Assign", receivers:["Worker-Plan"], performative:"reject-proposal", summary:"Bid closed · another worker scored higher", content:{worker_id:"Worker-Plan",utility:0.63}, status:"closed" },
  { time:"21:35:11.416", sender:"Broker-Assign", receivers:["Worker-Impl"], performative:"reject-proposal", summary:"Bid closed · another worker scored higher", content:{worker_id:"Worker-Impl",utility:0.66}, status:"closed" },
  { time:"22:05:14.832", sender:"Worker-Investigate", receivers:["Broker-Assign"], performative:"inform", summary:"Likely root cause: payment-db connection pool exhaustion", content:{ticket_id:"TCK-1042", finding:"Connection pool saturation", confidence:0.82}, status:"complete" },
];

const nodes = [
  { id:"Broker-Assign", role:"Broker", x:45, y:50, short:"Broker", label:"Broker-Assign · coordinator" },
  { id:"Worker-Plan", role:"Worker", x:81, y:18, short:"W · Plan", label:"Worker-Plan" },
  { id:"Worker-Investigate", role:"Worker", x:83, y:50, short:"W · Investigate", label:"Worker-Investigate" },
  { id:"Worker-Impl", role:"Worker", x:81, y:82, short:"W · Implement", label:"Worker-Impl" },
];
const toneByPerformative = { cfp:"violet", propose:"blue", "accept-proposal":"green", "reject-proposal":"muted", inform:"teal", refuse:"amber", failure:"red" };

function displayTime(value) {
  if (!value) return "just now";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("en-GB", { timeZone:"Asia/Jakarta", hour:"2-digit", minute:"2-digit", second:"2-digit" });
}

function messageSummary(message) {
  if (message.summary) return message.summary;
  const body = message.content || {};
  const detail = body.summary || body.finding || body.task;
  if (typeof detail === "string") return detail;
  if (body.worker_id && body.utility != null) return `${body.worker_id} · utility ${Number(body.utility).toFixed(2)}`;
  return `${Object.keys(body).length} content field${Object.keys(body).length === 1 ? "" : "s"} sent`;
}

function messageReceivers(message) {
  const list = message.receivers || message.receiver || [];
  return Array.isArray(list) ? list : [list];
}

function FlowMap({ message, selectedIndex, live, total, onSelectAgent, selectedAgent, zoom }) {
  const receivers = messageReceivers(message);
  const selectedNodes = new Set([message.sender, ...receivers]);
  const broadcast = receivers.length > 1;
  if (live) {
    const targets = receivers.slice(0,3);
    const targetY = targets.length === 1 ? [50] : targets.length === 2 ? [34,66] : [18,50,82];
    return <div className="comm-map" style={{width:`${Math.max(100,zoom*100)}%`,minWidth:`${760*zoom}px`,height:`${365*zoom}px`}} aria-label="Live agent communication route">
      <svg className="comm-routes" viewBox="0 0 1000 500" preserveAspectRatio="none" aria-hidden="true">
        <defs><marker id="live-comm-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="currentColor"/></marker></defs>
        {targets.map((_,index)=><g className="route-group route-active" key={index}><path d={`M 310 250 C 470 250, 525 ${targetY[index]*5}, 730 ${targetY[index]*5}`} markerEnd="url(#live-comm-arrow)"/><circle className="route-pulse" r="5"><animateMotion dur={`${1.6 + index*.2}s`} repeatCount="indefinite" path={`M 310 250 C 470 250, 525 ${targetY[index]*5}, 730 ${targetY[index]*5}`}/></circle></g>)}
      </svg>
      <button type="button" className={`comm-node live-sender ${selectedAgent===(message.sender||"Unknown agent")?"node-inspected":""}`} aria-pressed={selectedAgent===(message.sender||"Unknown agent")} onClick={()=>onSelectAgent(message.sender || "Unknown agent")}><span className="comm-node-icon broker"><Activity size={16}/></span><span><b>{message.sender || "Unknown agent"}</b><small>Message sender</small></span><i className="node-state"/></button>
      {targets.map((agent,index)=><button type="button" className={`comm-node live-recipient ${selectedAgent===agent?"node-inspected":""}`} style={{top:`${targetY[index]}%`}} key={`${agent}-${index}`} aria-pressed={selectedAgent===agent} onClick={()=>onSelectAgent(agent)}><span className="comm-node-icon worker-tone-2"><Bot size={16}/></span><span><b>{agent}</b><small>Message recipient</small></span><i className="node-state"/></button>)}
      {!targets.length&&<div className="live-no-recipient">No recipient listed in this ACL message</div>}
      {receivers.length>3&&<span className="live-extra-recipients">+{receivers.length-3} more recipients</span>}
      <div className="comm-map-footer"><span><i className="legend-dot active-dot"/>Published route</span><span><i className="legend-line"/>ACL delivery</span><small>LIVE MESSAGE · {selectedIndex + 1}/{total}</small></div>
    </div>;
  }
  return <div className="comm-map" style={{width:`${Math.max(100,zoom*100)}%`,minWidth:`${760*zoom}px`,height:`${365*zoom}px`}} aria-label="Agent communication network">
    <svg className="comm-routes" viewBox="0 0 1000 500" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <marker id="comm-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="currentColor"/></marker>
      </defs>
      <path className="orchestrator-route" d="M 260 250 C 320 250, 350 250, 420 250" markerEnd="url(#comm-arrow)"/>
      {[18,50,82].map((y,index)=><g key={y} className={`route-group ${selectedNodes.has(nodes[index+1].id) ? "route-active" : ""}`}>
        <path d={`M 430 250 C 570 250, 560 ${y*5}, 790 ${y*5}`} markerEnd="url(#comm-arrow)"/>
        {((broadcast && message.performative==="cfp") || selectedNodes.has(nodes[index+1].id)) && <circle className="route-pulse" r="5"><animateMotion dur={`${1.6 + index*.2}s`} repeatCount="indefinite" path={`M 430 250 C 570 250, 560 ${y*5}, 790 ${y*5}`}/></circle>}
        <path className="route-return" d={`M 790 ${y*5} C 610 ${y*5}, 620 250, 430 250`} markerEnd="url(#comm-arrow)"/>
      </g>)}
    </svg>
    <button type="button" className={`comm-node comm-orchestrator ${selectedNodes.has("Orchestrator")?"node-active":""} ${selectedAgent==="Orchestrator"?"node-inspected":""}`} aria-pressed={selectedAgent==="Orchestrator"} onClick={()=>onSelectAgent("Orchestrator")}>
      <span className="comm-node-icon orchestration"><GitBranch size={16}/></span><span><b>Orchestrator</b><small>Ticket TCK-1042</small></span><i className="node-state"/>
    </button>
    <button type="button" className={`comm-node comm-broker ${selectedNodes.has("Broker-Assign")?"node-active":""} ${selectedAgent==="Broker-Assign"?"node-inspected":""}`} aria-pressed={selectedAgent==="Broker-Assign"} onClick={()=>onSelectAgent("Broker-Assign")}>
      <span className="comm-node-icon broker"><Activity size={16}/></span><span><b>Broker</b><small>Broker-Assign · coordinator</small></span><i className="node-state"/>
    </button>
    {nodes.slice(1).map((node,index)=><button type="button" className={`comm-node comm-worker worker-${index+1} ${selectedNodes.has(node.id)?"node-active":""} ${selectedAgent===node.id?"node-inspected":""} ${message.performative === "accept-proposal" && message.content?.worker_id===node.id?"node-winner":""}`} key={node.id} aria-pressed={selectedAgent===node.id} onClick={()=>onSelectAgent(node.id)}>
      <span className={`comm-node-icon worker-icon worker-tone-${index+1}`}><Bot size={16}/></span><span><b>{node.short}</b><small>{node.label}</small></span>{message.performative === "accept-proposal" && message.content?.worker_id===node.id&&<i className="winner-mark"><Check size={11}/></i>}
    </button>)}
    <div className="comm-map-footer"><span><i className="legend-dot active-dot"/>Selected route</span><span><i className="legend-line"/>Available channel</span><small>REPLAY TOPOLOGY · {selectedIndex + 1}/{total}</small></div>
  </div>;
}

export default function CommunicationsPage({ liveMessages = [], connected = false }) {
  const [mode, setMode] = useState("replay");
  const [selectedIndex, setSelectedIndex] = useState(4);
  const [liveSelected, setLiveSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mapZoom, setMapZoom] = useState(1);
  const [selectedAgent, setSelectedAgent] = useState("Broker-Assign");
  const messages = useMemo(()=>mode === "replay" ? replayMessages : liveMessages.map(item=>({
    ...item, time:item.receivedAt, receivers:item.receiver || [], summary:messageSummary(item), status:"live",
  })),[mode,liveMessages]);
  const selected = messages[mode === "replay" ? selectedIndex : liveSelected] || messages[0];
  const proposalCount = replayMessages.filter(item=>item.performative === "propose").length;

  useEffect(()=>{
    if (!playing || mode !== "replay") return undefined;
    const timer = window.setInterval(()=>setSelectedIndex(index=>(index+1)%replayMessages.length), 1700);
    return ()=>window.clearInterval(timer);
  },[playing,mode]);

  useEffect(()=>{
    if (liveMessages.length) setMode("live");
  },[liveMessages[0]?.message_id]);

  const chooseMode = next => { setMode(next); setPlaying(false); };
  const selectMessage = index => mode === "replay" ? setSelectedIndex(index) : setLiveSelected(index);
  const content = selected?.content || {};
  const policy = selected?.policy || selected?.policy_context || {};
  const sender = selected?.sender || "Unknown agent";
  const receivers = selected ? messageReceivers(selected) : [];
  const receivedAt = selected?.receivedAt || selected?.time;
  const agentInspector = {
    "Orchestrator": {role:"Workflow controller", task:"Advance the ticket state and pause at policy checkpoints", capabilities:"Nine-stage state machine · approval queue · append-only audit"},
    "Scout-Feedback": {role:"Scout · feedback intake", task:"Normalize a user report into a traceable ticket", capabilities:"Input validation · PII masking · ticket persistence"},
    "Broker-Triage": {role:"Broker · severity triage", task:"Classify operational impact and provide the evidence behind it", capabilities:"Explainable severity cues · optional bounded LLM proposal · human escalation"},
    "Broker-Assign": {role:"Broker · worker allocation", task:"Compare worker bids and award the highest utility", capabilities:"Contract Net Protocol · skill, load, and cost scoring"},
    "broker-assign@orchestrator": {role:"Broker · worker allocation", task:"Compare worker bids and award the highest utility", capabilities:"Contract Net Protocol · skill, load, and cost scoring"},
    "Security-Policy": {role:"Security · autonomy gate", task:"Decide whether this severity and confidence may proceed autonomously", capabilities:"Deterministic confidence and risk checks · append-only decision audit"},
    "Worker-Plan": {role:"Worker · planning", task:"Break investigation findings into scoped tasks", capabilities:"Task decomposition · acceptance criteria"},
    "Worker-Investigate": {role:"Worker · investigation", task:"Rank likely causes from collected evidence", capabilities:"Root-cause ranking · evidence summaries"},
    "Worker-Impl": {role:"Worker · implementation", task:"Prepare an isolated change for review", capabilities:"Patch drafting · repository context"},
    "Worker-QA": {role:"Worker · verification", task:"Check proposed work against acceptance criteria", capabilities:"Focused test plan · pass/fail reporting · regression checks"},
    "Worker-Deploy": {role:"Worker · release", task:"Propose a cautious rollout after review", capabilities:"Canary plan · human release checkpoint · rollback criteria"},
    "Scout-Monitor": {role:"Scout · monitoring", task:"Check post-release health and return new signals to triage", capabilities:"SLO monitoring · anomaly reports · feedback loop"},
    "Human-Reviewer": {role:"Human · governance checkpoint", task:"Review a gated result and decide whether the pipeline may advance", capabilities:"Accept or reject · required note · decision audit"},
  }[selectedAgent] || {role:"Agent participant",task:"Inspect this message participant in the live stream",capabilities:"Role capabilities depend on the connected runtime."};

  return <div className="page-wrap communications-page">
    <Heading eyebrow="Multi-agent observability · protocol monitor" title="Agent communications" subtitle={mode === "replay"?"Follow how agents delegate, negotiate, and hand off work for one ticket run.":"Follow published ACL messages across the live agent fleet."} action={<div className="run-badge"><span className="run-badge-icon"><Activity size={15}/></span><span><small>{mode === "replay" ? "SAMPLE REPLAY" : "LIVE ACL STREAM"}</small><b>{mode === "replay" ? <>TCK-1042 <i>·</i> Flash sale checkout</> : "Across all agent runs"}</b></span>{mode === "replay"&&<span className="run-severity">CRITICAL</span>}</div>}/>

    <div className="comm-overview">
      <Panel className="comm-stat"><span className="comm-stat-icon stat-violet"><MessageSquareText size={16}/></span><span><small>{mode === "replay"?"Messages in run":"Messages captured"}</small><b>{mode === "replay" ? "08" : String(liveMessages.length).padStart(2,"0")}</b></span><em>{mode === "replay" ? "Protocol replay" : "Live stream"}</em></Panel>
      <Panel className="comm-stat"><span className="comm-stat-icon stat-blue"><Users size={16}/></span><span><small>Agents involved</small><b>{mode === "replay" ? "04" : String(new Set(liveMessages.flatMap(item=>[item.sender,...(item.receiver||[])])).size).padStart(2,"0")}</b></span><em>{mode === "replay"?"1 broker · 3 workers":"Across live messages"}</em></Panel>
      <Panel className="comm-stat"><span className={`comm-stat-icon ${mode === "replay"?"stat-green":"stat-violet"}`}>{mode === "replay"?<CheckCheck size={16}/>:<MessageSquareText size={16}/>}</span><span><small>{mode === "replay"?"Assignment outcome":"Latest performative"}</small><b>{mode === "replay"?"Worker-Investigate":selected?.performative?.toUpperCase()||"Waiting"}</b></span><em>{mode === "replay"?"Highest utility · 0.69":selected?.correlation_id||"No messages yet"}</em></Panel>
      <Panel className="comm-stat comm-health"><span className={`comm-stat-icon ${connected?"stat-green":"stat-amber"}`}><Radio size={16}/></span><span><small>Live event stream</small><b>{connected?"Connected":"Standby"}</b></span><em><i className={connected?"connected-dot":"standby-dot"}/>{connected?"SSE connected":"Waiting for events"}</em></Panel>
    </div>

    <div className="comm-toolbar">
      <div><SectionTitle title="Communication flow" detail={mode === "replay"?"A labeled sample Contract Net conversation. Start a Ticket Test and select Live stream to follow actual run handoffs.":"Live routes for ACL messages emitted by the active ticket workflow."}/></div>
      <div className="comm-controls" role="group" aria-label="Communication display mode">
        <button className={mode === "replay" ? "selected" : ""} onClick={()=>chooseMode("replay")}>Protocol replay <span>08</span></button>
        <button className={mode === "live" ? "selected" : ""} onClick={()=>chooseMode("live")}>Live stream <span>{liveMessages.length}</span></button>
      </div>
    </div>

    <div className="comm-workspace">
      <Panel className="comm-map-panel">
        <div className="comm-panel-heading"><div><small className="eyebrow">AGENT TOPOLOGY</small><h2>Who is talking to whom</h2></div><span className={`replay-label ${mode === "live" ? "is-live" : ""}`}><i/>{mode === "live" ? "LIVE" : "REPLAY"}</span></div>
        <div className="comm-map-tools"><span><Maximize2 size={13}/>Scroll the map to inspect the network; select a node for its role.</span><div><button type="button" onClick={()=>setMapZoom(value=>Math.max(.8,Number((value-.2).toFixed(1))))} aria-label="Zoom out"><ZoomOut size={14}/></button><button type="button" onClick={()=>setMapZoom(1)} aria-label="Reset map zoom">{Math.round(mapZoom*100)}%</button><button type="button" onClick={()=>setMapZoom(value=>Math.min(1.8,Number((value+.2).toFixed(1))))} aria-label="Zoom in"><ZoomIn size={14}/></button></div></div>
        {selected ? <div className="comm-map-viewport"><FlowMap message={selected} selectedIndex={mode === "replay" ? selectedIndex : liveSelected} live={mode === "live"} total={messages.length} onSelectAgent={setSelectedAgent} selectedAgent={selectedAgent} zoom={mapZoom}/></div> : <div className="comm-map comm-map-empty"><MessageSquareText size={24}/><b>No published messages yet</b><span>Messages posted to the agent bus will appear here as they are published.</span></div>}
        <div className="comm-agent-inspector"><span className="comm-agent-avatar"><Bot size={15}/></span><span><small>SELECTED AGENT · {selectedAgent}</small><b>{agentInspector.role}</b></span><div><small>CURRENT TASK</small><b>{agentInspector.task}</b></div><div><small>CAPABILITIES</small><b>{agentInspector.capabilities}</b></div></div>
        <div className="protocol-strip"><span className="protocol-mark"><Sparkles size={14}/></span><span><b>{mode === "replay"?"Contract Net Protocol":"FIPA-ACL message"}</b><small>{mode === "replay"?"CFP → proposals → award → task result":"Performative · sender · recipients · correlation"}</small></span><span className="protocol-rule"/><span className="protocol-note"><ShieldCheck size={13}/>{mode === "replay"?"Policy context attached":"Per-message policy context"}</span></div>
      </Panel>

      <Panel className="comm-timeline-panel">
        <div className="comm-panel-heading timeline-heading"><div><small className="eyebrow">MESSAGE SEQUENCE</small><h2>{mode === "replay" ? "Assignment conversation" : "Published messages"}</h2></div>{mode === "replay" && <button className={`replay-button ${playing?"playing":""}`} onClick={()=>setPlaying(value=>!value)} aria-label={playing?"Pause replay":"Play replay"}>{playing?<Pause size={13}/>:<Play size={13}/>}<span>{playing?"Pause":"Play"}</span></button>}</div>
        <div className="comm-thread-meta"><span><Clock3 size={12}/>{mode === "replay" ? "14 Sep 2026 · 21:35–22:05 WIB" : "Asia/Jakarta · newest first"}</span><span><CircleDot size={10}/>{mode === "replay" ? "Correlation · TCK-1042" : connected ? "SSE connected" : "SSE disconnected"}</span></div>
        {messages.length ? <div className="message-sequence" role="list" aria-label="Agent messages">
          {messages.map((message,index)=>{
            const active = mode === "replay" ? selectedIndex === index : liveSelected === index;
            const recipientList = messageReceivers(message);
            return <button key={message.message_id || `${message.time}-${index}`} className={`message-event ${active?"active":""} ${message.status === "selected"?"event-winner":""}`} onClick={()=>selectMessage(index)} role="listitem" aria-current={active?"true":undefined}>
              <span className={`message-symbol perf-${toneByPerformative[message.performative]||"muted"}`}>{message.performative === "cfp"?<Radio size={13}/>:message.performative === "propose"?<ArrowRight size={13}/>:message.performative === "accept-proposal"?<Check size={13}/>:message.performative === "inform"?<MessageSquareText size={13}/>:<ArrowDown size={13}/>}</span>
              <span className="message-event-body"><span className="message-event-top"><b>{message.performative}</b><time>{displayTime(message.time)}</time></span><span className="message-route"><b>{message.sender || "Unknown agent"}</b><ArrowRight size={12}/><span>{recipientList.length > 1 ? `${recipientList[0]} +${recipientList.length-1}` : recipientList[0] || "No recipient"}</span></span><small>{messageSummary(message)}</small></span>
              {message.status === "selected" && <span className="winner-pill">SELECTED</span>}
              {mode === "live" && <span className="live-event-dot"/>}
            </button>;
          })}
        </div> : <div className="live-empty"><span><Radio size={17}/></span><b>Listening for agent messages</b><p>Published ACL messages will show their sender, recipients, performative, and correlation ID here.</p><small>{connected?"The event stream is connected.":"Connect the API event stream to watch live traffic."}</small></div>}
      </Panel>
    </div>

    {selected && <Panel className="message-inspector">
      <div className="inspector-title"><span className={`inspector-icon perf-${toneByPerformative[selected.performative]||"muted"}`}><MessageSquareText size={15}/></span><span><small className="eyebrow">SELECTED MESSAGE · {mode === "replay" ? "REPLAY" : "LIVE"}</small><h2>{selected.performative}</h2></span><Tag tone={selected.performative === "accept-proposal"?"green":selected.performative === "cfp"?"purple":"neutral"}>{selected.performative === "accept-proposal"?"Awarded":selected.performative === "cfp"?"Broadcast":"Agent message"}</Tag></div>
      <div className="inspector-grid">
        <div className="inspector-route"><small>ROUTE</small><div><span className="route-agent"><Bot size={13}/>{sender}</span><ArrowRight size={14}/><span className="route-agent"><Bot size={13}/>{receivers.join(", ") || "—"}</span></div></div>
        <div><small>TIME · WIB</small><b>{displayTime(receivedAt)}</b></div>
        <div><small>CORRELATION ID</small><b>{selected.correlation_id || (mode === "replay" ? "TCK-1042" : "—")}</b></div>
        <div><small>MESSAGE ID</small><b className="message-id">{selected.message_id || `replay-${String((mode === "replay" ? selectedIndex : liveSelected)+1).padStart(3,"0")}`}</b></div>
        <div className="inspector-payload"><small>CONTENT PAYLOAD</small><pre>{JSON.stringify(content,null,2)}</pre></div>
        <div className="inspector-policy"><small>POLICY CONTEXT</small>{Object.keys(policy).length ? <pre>{JSON.stringify(policy,null,2)}</pre> : <span>No policy context supplied with this message.</span>}</div>
      </div>
    </Panel>}

    <div className="comm-legend"><span><i className="legend-cfp"/>CFP · request for proposals</span><span><i className="legend-propose"/>PROPOSE · worker bid</span><span><i className="legend-award"/>ACCEPT · selected worker</span><span className="comm-legend-note">{mode === "replay" ? `${proposalCount} worker bids compared using utility = 0.5 skill + 0.3 (1 − load) + 0.2 (1 − cost)` : "Live view shows messages published through the ACL message bus."}</span></div>
  </div>;
}
