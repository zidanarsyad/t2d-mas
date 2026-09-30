import { useMemo, useState } from "react";
import {
  ArrowRight,
  Bot,
  MapPin,
  Play,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { agents } from "../data";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";
import OutputSummary from "../components/OutputSummary";
import { workflow } from "../workflow";
import { request } from "../api";
const purposes = {
  "Scout-Feedback": "Collects and normalizes issue reports.",
  "Broker-Triage": "Assesses impact and explains the severity.",
  "Broker-Assign": "Compares worker bids and allocates a task.",
  "Scout-Log":
    "Takes analysis to the data node and returns aggregate evidence.",
  "Worker-Investigate": "Suggests likely causes from the ticket’s wording.",
  "Worker-Plan": "Turns findings into tasks and acceptance criteria.",
  "Worker-Impl": "Drafts a change request. Repository tools are not connected.",
  "Worker-QA": "Prepares a test checklist. A CI runner is not connected.",
  "Worker-Deploy":
    "Proposes a cautious rollout. Production deployment is not connected.",
  "Scout-Monitor":
    "Defines the feedback loop. Live telemetry is not connected.",
  "Security-Policy": "Enforces confidence, risk, and human approval rules.",
};
const roleDescriptions = {
  Scout: "Collects information",
  Broker: "Coordinates decisions",
  Worker: "Produces a specialist result",
  Security: "Enforces review and data policies",
};
export default function AgentsPage({ records = [] }) {
  const [selectedId, setSelectedId] = useState("Scout-Log"),
    [filter, setFilter] = useState("All"),
    [node, setNode] = useState("1"),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState(null),
    [error, setError] = useState("");
  const selected = agents.find((item) => item.id === selectedId),
    visible = useMemo(
      () =>
        agents.filter(
          (item) => filter === "All" || item.mode === filter.toUpperCase(),
        ),
      [filter],
    );
  const stage = workflow.find((item) => item.agent === selectedId);
  const assignments = stage
    ? records.filter(
        (item) =>
          item.current_stage === stage.id &&
          !["completed", "rejected"].includes(item.status),
      )
    : [];
  async function migrate() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await request(`/demo/migrate/${node}`, "POST"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-wrap">
      <Heading
        eyebrow="Specialist roles"
        title="Meet the agent team"
        subtitle="Understand each agent’s responsibility, how it shares work, and where mobile execution fits."
        action={<Tag tone="purple">11 designed roles · 4 agent families</Tag>}
      />
      <div className="agent-family-grid">
        {Object.entries(roleDescriptions).map(([role, description]) => (
          <Panel key={role}>
            <Bot size={21} />
            <b>{role}</b>
            <span>{description}</span>
          </Panel>
        ))}
      </div>
      <div className="catalog-layout">
        <Panel className="catalog-list">
          <div className="focus-heading">
            <SectionTitle title="Choose an agent" />
            <select
              aria-label="Filter agent execution model"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option>All</option>
              <option>Static</option>
              <option>Mobile</option>
            </select>
          </div>
          {visible.map((item) => (
            <button
              className={`catalog-agent ${selectedId === item.id ? "selected" : ""}`}
              key={item.id}
              onClick={() => setSelectedId(item.id)}
            >
              <span className={`agent-avatar role-${item.role.toLowerCase()}`}>
                {item.mode === "MOBILE" ? (
                  <Smartphone size={21} />
                ) : (
                  <Bot size={21} />
                )}
              </span>
              <span>
                <b>{item.id}</b>
                <small>{purposes[item.id]}</small>
              </span>
              <Tag tone={item.mode === "MOBILE" ? "purple" : "neutral"}>
                {item.mode === "MOBILE" ? "Mobile design" : "Static"}
              </Tag>
            </button>
          ))}
        </Panel>
        <div className="catalog-details">
          <Panel>
            <small className="eyebrow">
              {selected.role} · {roleDescriptions[selected.role]}
            </small>
            <h2>{selected.id}</h2>
            <p>{purposes[selected.id]}</p>
            <div className="checkpoint-callout">
              {selected.mode === "MOBILE" ? (
                <Smartphone size={24} />
              ) : (
                <MapPin size={24} />
              )}
              <div>
                <b>
                  {selected.mode === "MOBILE"
                    ? "Computation moves to the data"
                    : "Computation stays in one place"}
                </b>
                <p>
                  {selected.mode === "MOBILE"
                    ? "The design sends code and state to a data node, then returns an allowed summary. The Scout-Log demo below exercises a signed bundle on a container node."
                    : "This agent runs centrally and shares its result through the message bus."}
                </p>
              </div>
            </div>
            {stage && (
              <>
                <SectionTitle title="Tickets currently at this stage" />
                {assignments.length ? (
                  assignments.map((item) => (
                    <p key={item.ticket_id}>
                      {item.ticket_id} · {item.title}
                    </p>
                  ))
                ) : (
                  <p className="muted">
                    No active tickets at this agent’s stage.
                  </p>
                )}
              </>
            )}
            <small className="muted">
              This catalog describes roles and configured workflow stages. Host
              heartbeats and workload telemetry are not connected.
            </small>
          </Panel>
          {selectedId === "Scout-Log" && (
            <Panel className="mobile-demo">
              <SectionTitle
                title="Try a mobile agent"
                detail="Send a signed Scout-Log bundle to one of six local demo nodes."
              />
              <div className="mobile-demo-controls">
                <label>
                  Destination
                  <select
                    aria-label="Mobile agent destination"
                    value={node}
                    onChange={(event) => setNode(event.target.value)}
                    disabled={busy}
                  >
                    {[1, 2, 3, 4, 5, 6].map((value) => (
                      <option key={value} value={value}>
                        Node {value}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={migrate}
                >
                  <Play size={16} />
                  {busy ? "Running on node…" : "Run mobile demo"}
                </button>
              </div>
              <p className="muted">
                Demo input is synthetic. The returned measurements are
                aggregates; raw data stays at the node.
              </p>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              {result && (
                <div role="status">
                  <div className="mobile-route">
                    Orchestrator
                    <ArrowRight size={16} />
                    Node {result.node_id}
                    <ArrowRight size={16} />
                    Aggregate result
                  </div>
                  <OutputSummary output={result.result} />
                  <p className="muted">
                    Session network counters:{" "}
                    {result.bytes_sent.toLocaleString()} bytes sent ·{" "}
                    {result.bytes_returned.toLocaleString()} bytes returned.
                  </p>
                  <span className="policy-inline">
                    <ShieldCheck size={16} />
                    Signed bundle verified · allowed aggregate fields returned
                  </span>
                </div>
              )}
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
