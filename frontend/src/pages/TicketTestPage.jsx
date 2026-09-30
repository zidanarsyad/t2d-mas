import { useEffect, useRef, useState } from "react";
import { Activity, ArrowRight, Check, CircleStop, Play, RotateCcw, ShieldCheck, X } from "lucide-react";
import { Heading, Panel, SectionTitle, Severity } from "../components/Primitives";

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const stageLabel = value => value === "qa" ? "QA" : value[0].toUpperCase() + value.slice(1);
const demoTicket = {
  title: "Checkout service returns data corruption during flash sale",
  body: "During the flash sale, the checkout service reports data corruption for customer orders. The issue affects live order processing and needs investigation before any release. Please identify likely causes, propose a scoped fix, and list verification and rollback checks.",
};

export default function TicketTestPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [record, setRecord] = useState(null);
  const [reviewNote, setReviewNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const autoRun = useRef(false);

  useEffect(() => () => { autoRun.current = false; }, []);

  async function request(path, method = "GET", payload) {
    const response = await fetch(`/api${path}`, {
      method,
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "The ticket test request failed.");
    return data;
  }

  async function start(event) {
    event.preventDefault();
    autoRun.current = false;
    setBusy(true); setError(""); setNotice(""); setRecord(null); setReviewNote("");
    try {
      const next = await request("/sandbox/tickets", "POST", { title, body });
      setRecord(next);
      setNotice("Ticket accepted into the manual test pipeline.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function advance() {
    if (!record) return null;
    const next = await request(`/sandbox/tickets/${record.ticket_id}/advance`, "POST");
    setRecord(next);
    if (next.status === "waiting_for_review") autoRun.current = false;
    if (next.status === "completed" || next.status === "rejected") autoRun.current = false;
    return next;
  }

  async function step() {
    setBusy(true); setError(""); setNotice("");
    try {
      const next = await advance();
      if (next?.status === "waiting_for_review") setNotice(`Paused at ${next.waiting_for.replaceAll("_", " ")} for your decision.`);
      else if (next?.status === "completed") setNotice("All nine prototype stages completed. No production deployment was run.");
      else if (next?.status === "rejected") setNotice("This ticket was rejected and the pipeline is stopped.");
      else if (next) setNotice(`Moved to ${stageLabel(next.current_stage)}.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function runAutomatically() {
    setBusy(true); setError(""); setNotice("Running through stages; the pipeline will pause for human review.");
    autoRun.current = true;
    try {
      while (autoRun.current) {
        const next = await advance();
        if (!next || next.status !== "running") break;
        await pause(850);
      }
    } catch (err) { setError(err.message); }
    finally { autoRun.current = false; setBusy(false); }
  }

  function stopAutomatically() { autoRun.current = false; setNotice("Automatic progression stopped."); }

  async function decide(intent) {
    if (reviewNote.trim().length < 3) { setError("Add a short reviewer note before recording this decision."); return; }
    setBusy(true); setError(""); setNotice(""); autoRun.current = false;
    try {
      const next = await request(`/sandbox/tickets/${record.ticket_id}/review`, "POST", {
        approver: "manual-test-reviewer", approved: intent === "accept", intent, reason: reviewNote.trim(),
      });
      setRecord(next); setReviewNote("");
      const latest = next.reviews.at(-1);
      if (latest?.decision === "clarification_requested") {
        setNotice(latest.interpretation?.clarification_question || "The feedback needs clarification. Add a more specific reviewer note.");
      } else if (intent === "accept") setNotice(`Accepted at ${latest?.checkpoint?.replaceAll("_", " ")}; pipeline resumed.`);
      else if (intent === "request_changes") setNotice(`Feedback interpreted and ${latest?.stage} revised. Review the updated output, then advance the pipeline.`);
      else setNotice("Rejected with your note; the pipeline stopped at this step.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function reset() { autoRun.current = false; setRecord(null); setNotice(""); setError(""); setReviewNote(""); }

  return <div className="page-wrap">
    <Heading eyebrow="Interactive pipeline sandbox" title="Ticket test" subtitle="Follow nine agent stages, inspect each saved output and handoff, then record human decisions with notes." action={record && <button className="button secondary" onClick={reset}><RotateCcw size={14}/>New test</button>}/>
    <Panel className="test-disclaimer"><ShieldCheck size={17}/><span><b>Local multi-agent prototype</b><small>Each stage produces an auditable local result and sends an ACL handoff visible in Agent Communications. Investigation uses ticket-text heuristics; planning is templated; implementation, QA, deployment, and monitoring are drafts or simulations because repository, CI, production, and telemetry tools are not connected. Rule severity scores are not calibrated probabilities. Email, phone, and common token patterns are masked before project history is saved; ticket and reviewer text are sent to OpenRouter when its key is configured.</small></span></Panel>
    {!record && <Panel className="test-form-panel"><SectionTitle title="Original ticket" detail="This exact title and description stay attached to the run as it moves through the stages."/><form className="test-ticket-form" onSubmit={start}>
      <label className="test-title-field">Ticket title<input required minLength={3} maxLength={180} value={title} onChange={event => setTitle(event.target.value)} placeholder="e.g. Checkout fails for saved cards"/></label>
      <label className="test-description-field">Original description<textarea required minLength={10} maxLength={4000} rows={6} value={body} onChange={event => setBody(event.target.value)} placeholder="Describe what happened, steps to reproduce, expected behavior, and impact…"/><small>{body.length}/4000 characters · the triage agent infers severity from this text</small></label>
      {error && <p className="test-error" role="alert">{error}</p>}
      <div className="test-form-actions"><button className="button secondary" type="button" onClick={() => { setTitle(demoTicket.title); setBody(demoTicket.body); setError(""); }}>Load demo ticket</button><button className="button primary" type="submit" disabled={busy}><Play size={14}/>Start ticket test</button></div>
    </form></Panel>}
    {record && <div className="test-workspace">
      <Panel className="test-original"><div className="test-original-top"><div><small className="eyebrow">Original ticket · {record.ticket_id}</small><h2>{record.title}</h2></div><span className={`test-agent-severity ${record.severity.toLowerCase()}`}><small>Severity decided by triage agent</small><span><Severity value={record.severity}/><b>Rule score {record.severity_confidence.toFixed(2)}</b></span></span></div><p>{record.body}</p><div className="test-triage-rationale"><b>Agent rationale</b><span>{record.severity_rationale}</span></div></Panel>
      {notice && <div className="test-notice" role="status"><Activity size={14}/>{notice}</div>}
      {error && <div className="test-error test-notice" role="alert"><X size={14}/>{error}</div>}
      <Panel className="test-process-panel"><div className="test-process-heading"><SectionTitle title="Live process" detail={`${record.status.replaceAll("_", " ")} · current step: ${stageLabel(record.current_stage)}`}/><div className="test-process-actions">
        {record.status === "running" && <><button className="button secondary" onClick={step} disabled={busy}><ArrowRight size={14}/>Advance one step</button><button className="button primary" onClick={runAutomatically} disabled={busy}><Play size={14}/>Run automatically</button></>}
        {busy && autoRun.current && <button className="button secondary" onClick={stopAutomatically}><CircleStop size={14}/>Stop</button>}
      </div></div>
        <ol className="test-stage-list">{record.stages.map((item, index) => <li key={item.name} className={`test-stage ${item.status}`}><span className="stage-step">{item.status === "completed" ? <Check size={12}/> : String(index + 1).padStart(2, "0")}</span><div><b>{stageLabel(item.name)}</b><small>{item.status === "current" ? "In progress" : item.status === "completed" ? "Completed" : item.status === "rejected" ? "Stopped after rejection" : "Upcoming"}</small></div>{item.name === record.current_stage && record.waiting_for && <span className="test-stage-gate"><ShieldCheck size={12}/>{record.waiting_for.replaceAll("_", " ")}</span>}</li>)}</ol>
      </Panel>
      {record.status === "waiting_for_review" && <Panel className="test-review-panel"><SectionTitle title="Human review required" detail={`${record.waiting_for.replaceAll("_", " ")} · the pipeline is paused until you decide.`}/><div className="test-review-prediction"><b>Agent severity: {record.severity} · rule score {record.severity_confidence.toFixed(2)}</b><span>{record.severity_rationale}</span></div><label>Reviewer note<textarea rows={3} maxLength={500} value={reviewNote} onChange={event => setReviewNote(event.target.value)} placeholder="Explain the decision, correction, evidence, or constraint…"/><small>{reviewNote.length}/500 · required for each decision</small></label><p className="review-feedback-explainer">Accept continues with this result. Request changes sends your note to the responsible agent to interpret and revise its proposal; ambiguous feedback will be returned for clarification. Reject stops the run. Review notes, interpreted intent, and revisions are saved in ticket history.</p><div className="test-review-actions"><button className="button reject" onClick={() => decide("reject")} disabled={busy || reviewNote.trim().length < 3}><X size={14}/>Reject and stop</button><button className="button secondary" onClick={() => decide("request_changes")} disabled={busy || reviewNote.trim().length < 3}><RotateCcw size={14}/>Request changes</button><button className="button approve" onClick={() => decide("accept")} disabled={busy || reviewNote.trim().length < 3}><Check size={14}/>Accept and continue</button></div></Panel>}
      {record.reviews.length > 0 && <Panel className="test-review-history"><SectionTitle title="Review history" detail="Decisions, interpreted intent, and revised proposals are saved to the project audit log."/>{record.reviews.map((item, index) => <div className={`test-review-item ${item.intent === "accept" ? "accepted" : "rejected"}`} key={`${item.checkpoint}-${index}`}><b>{item.decision.replaceAll("_", " ")} · {item.checkpoint.replaceAll("_", " ")}{item.revision ? ` · revision ${item.revision}` : ""}</b><small>{item.approver}</small><p>{item.note}</p>{item.interpretation && <p><b>Agent interpretation:</b> {item.interpretation.summary}{item.interpretation.needs_clarification && ` · ${item.interpretation.clarification_question}`}</p>}{item.intent === "request_changes" && record.agent_outputs?.[item.stage] && <pre>{JSON.stringify(record.agent_outputs[item.stage], null, 2)}</pre>}</div>)}</Panel>}
    </div>}
  </div>;
}
