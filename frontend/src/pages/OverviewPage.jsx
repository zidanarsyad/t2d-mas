import { ArrowRight, Beaker, CheckCircle2, FlaskConical, ShieldCheck, Workflow } from "lucide-react";
import { Heading, Panel, SectionTitle } from "../components/Primitives";

const phases = [
  {
    title: "1. Understand the report",
    description: "Turn incoming feedback into a clear piece of work.",
    steps: [
      { title: "Intake", detail: "Capture the user's issue." },
      { title: "Triage", detail: "Assess urgency; duplicate search remains a separate module.", gate: "Confirm the impact assessment" },
      { title: "Assignment", detail: "Choose the right team." },
      { title: "Investigation", detail: "Look for evidence and a likely cause." },
    ],
  },
  {
    title: "2. Prepare and check a fix",
    description: "Specialists prepare a proposed change and quality checks.",
    steps: [
      { title: "Planning", detail: "Describe the work and success criteria." },
      { title: "Implementation", detail: "Prepare a draft change." },
      { title: "QA checks", detail: "Review proposed tests and risks.", gate: "Review the proposed change" },
    ],
  },
  {
    title: "3. Release and learn",
    description: "Release decisions stay with people; service health informs future work.",
    steps: [
      { title: "Deployment", detail: "Plan a cautious release.", gate: "Approve the release proposal" },
      { title: "Monitoring", detail: "Share simulated observations back with triage." },
    ],
  },
];

export default function OverviewPage({ onNavigate }) {
  return <div className="page-wrap overview-page">
    <Heading
      eyebrow="Start here · project guide"
      title="From feedback to a safer release"
      subtitle="T2D-MAS helps a software team sort a reported issue, prepare a fix, and review important decisions before release."
      action={<div className="overview-actions"><button className="button secondary" onClick={() => onNavigate("experiments")}><FlaskConical size={14}/>Compare A0–A3</button><button className="button primary" onClick={() => onNavigate("test")}><Beaker size={14}/>Try a sample ticket</button></div>}
    />

    <Panel className="overview-purpose">
      <span className="overview-purpose-icon"><Workflow size={20}/></span>
      <div><small>WHAT THIS PROJECT DOES</small><b>One guided workflow, with people reviewing key decisions.</b><p>Specialist software agents help with the hand-offs from an incoming issue to a proposed release. A person reviews impact, the proposed change, and the release proposal.</p></div>
    </Panel>

    <div className="overview-facts">
      <Panel><span className="overview-fact-icon"><Workflow size={17}/></span><div><b>9 steps</b><small>From report intake through service monitoring</small></div></Panel>
      <Panel><span className="overview-fact-icon"><ShieldCheck size={17}/></span><div><b>3 human reviews</b><small>Impact, proposed change, and release</small></div></Panel>
      <Panel><span className="overview-fact-icon"><CheckCircle2 size={17}/></span><div><b>Course prototype</b><small>Some checks and outcomes are simulated or drafted</small></div></Panel>
    </div>

    <div className="overview-section-heading"><SectionTitle title="How a ticket moves through the system" detail="Read each row from left to right. Numbered steps make up the nine-stage workflow."/></div>
    <div className="overview-phases">
      {phases.map((phase, phaseIndex) => <Panel className="overview-phase" key={phase.title}>
        <div className="overview-phase-title"><span>{String(phaseIndex + 1).padStart(2, "0")}</span><div><h2>{phase.title}</h2><p>{phase.description}</p></div></div>
        <ol className="overview-stage-flow">
          {phase.steps.map((step, stepIndex) => <li className="overview-stage-item" key={step.title}>
            <div className="overview-stage-card"><span>{String(phases.slice(0, phaseIndex).reduce((total, item) => total + item.steps.length, 0) + stepIndex + 1).padStart(2, "0")}</span><b>{step.title}</b><small>{step.detail}</small></div>
            {step.gate && <div className="overview-checkpoint"><ShieldCheck size={13}/><span><b>Human review</b><small>{step.gate}</small></span></div>}
            {stepIndex < phase.steps.length - 1 && <ArrowRight className="overview-flow-arrow" size={16} aria-hidden="true"/>}
          </li>)}
        </ol>
      </Panel>)}
    </div>

    <Panel className="overview-scope"><ShieldCheck size={17}/><div><b>People can pause high-risk decisions.</b><p>When confidence is low or a proposed action carries too much risk, the workflow asks a person to review it. This classroom prototype can prepare plans and release proposals, but it does not run a connected production deployment.</p></div></Panel>
  </div>;
}
