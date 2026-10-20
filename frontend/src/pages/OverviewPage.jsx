import { useMemo } from "react";
import { CircleCheck, CirclePlay, FlaskConical, ShieldCheck, TriangleAlert, Workflow } from "lucide-react";
import PipelineFlow from "../components/PipelineFlow";
import Term from "../components/Term";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";
import { replayFrames } from "../lib/flow.js";
import { gates, phases, stages } from "../lib/workflow.js";
import { sampleConversation, sampleIntro, sampleOutro } from "../data/sampleConversation.js";
import { ideaVsPrototype } from "../data/reportExamples.js";
import { useStepPlayer } from "../hooks/useStepPlayer";

const STATUS_TAG = {
  real: { tone: "green", icon: CircleCheck, label: "Real" },
  mixed: { tone: "amber", icon: TriangleAlert, label: "Mixed" },
  simulated: { tone: "violet", icon: FlaskConical, label: "Simulated" },
};

export default function OverviewPage({ workspace, onNavigate }) {
  const { policy } = workspace;
  const frames = useMemo(() => replayFrames(sampleConversation, { intro: sampleIntro, outro: sampleOutro, policy }), [policy]);
  // One autoplay per page: the story starts by itself unless the user prefers reduced motion.
  const player = useStepPlayer(frames, { autoPlay: true });
  const always = gates.filter((gate) => !gate.conditional).length;

  return (
    <div className="page">
      <Heading
        eyebrow="Start here"
        title="From user feedback to a safer release"
        what="A replay of one flash-sale incident (TCK-1042) as nine agents hand it from stage to stage."
        why="It shows where agents may act alone and where a person must decide."
        action={
          <>
            <button type="button" className="button" onClick={() => onNavigate("experiments")}>
              <FlaskConical size={16} aria-hidden="true" />
              Compare A0–A3
            </button>
            <button type="button" className="button button-primary" onClick={() => onNavigate("run")}>
              <CirclePlay size={16} aria-hidden="true" />
              Run a ticket
            </button>
          </>
        }
      />

      <Panel>
        <PipelineFlow frame={player.step} player={player} source="replay" title="TCK-1042: checkout crashes in the 10.10 flash sale" ticketLabel="TCK-1042" policy={policy} />
      </Panel>

      <div className="fact-row">
        <Panel className="fact">
          <Workflow size={18} aria-hidden="true" />
          <div>
            <b>{stages.length} stages</b>
            <small>From feedback capture to monitoring, then back to triage</small>
          </div>
        </Panel>
        <Panel className="fact">
          <ShieldCheck size={18} aria-hidden="true" />
          <div>
            <b>{gates.length} human gates</b>
            <small>
              {always} always ask a person; {gates.length - always} only when a rule fails, like the <Term id="autonomy-gate">autonomy gate</Term>
            </small>
          </div>
        </Panel>
        <Panel className="fact">
          <FlaskConical size={18} aria-hidden="true" />
          <div>
            <b>Course prototype</b>
            <small>Some stages are simulated with seeded data; every page says which</small>
          </div>
        </Panel>
      </div>

      <SectionTitle title="The nine stages in three phases" detail="Each stage has one responsible agent. Select Run a ticket to watch a real run." />
      <div className="phase-grid">
        {phases.map((phase) => (
          <Panel key={phase.id} className="phase">
            <h3>{phase.name}</h3>
            <p className="muted">{phase.description}</p>
            <ol className="phase-stages">
              {stages
                .filter((stage) => stage.phase === phase.id)
                .map((stage) => (
                  <li key={stage.id}>
                    <b>
                      {stages.indexOf(stage) + 1}. {stage.name}
                    </b>
                    <span>{stage.plain}</span>
                    <small>{stage.agent}</small>
                  </li>
                ))}
            </ol>
          </Panel>
        ))}
      </div>

      <Panel>
        <SectionTitle title="Idea vs prototype" detail="What the report designed, and what this prototype really runs." />
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Area</th>
                <th scope="col">The idea</th>
                <th scope="col">In this prototype</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {ideaVsPrototype.map((row) => {
                const status = STATUS_TAG[row.status];
                return (
                  <tr key={row.area}>
                    <th scope="row">{row.area}</th>
                    <td>{row.idea}</td>
                    <td>{row.prototype}</td>
                    <td>
                      <Tag tone={status.tone} icon={status.icon}>
                        {status.label}
                      </Tag>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
