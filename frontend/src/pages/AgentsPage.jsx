import { useMemo, useState } from "react";
import { Bot, MapPin, Smartphone } from "lucide-react";
import { api } from "../api";
import MobileAgentMap from "../components/MobileAgentMap";
import Term from "../components/Term";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";
import { agents, families } from "../data/agents.js";
import { mobileCostModel, modelTrip, NODE_SERVICES, REPORT_INPUTS, tripFromMigrations } from "../lib/mobileTrip.js";
import { shortAgentName, stageInfo, stageOfAgent } from "../lib/workflow.js";
import { useReducedMotion } from "../hooks/useReducedMotion";

// The signed bundle takes this long to fly to a node in the trip animation (see MobileAgentMap).
const BUNDLE_TRAVEL_MS = 900;
const COMPONENTS = ["perceive", "remember", "reason", "act", "report"];
const SIMULATED_TAG = {
  false: { tone: "green", label: "Real logic" },
  mixed: { tone: "amber", label: "Real + simulated" },
  true: { tone: "violet", label: "Simulated tools" },
};

export default function AgentsPage({ workspace }) {
  const { records, policy, mode, health } = workspace;
  const [selectedId, setSelectedId] = useState("Scout-Log");
  const [filter, setFilter] = useState("all");
  const [tripMode, setTripMode] = useState("mobile");
  const [liveTrip, setLiveTrip] = useState(null);
  const [investigating, setInvestigating] = useState(false);
  const reduced = useReducedMotion();
  const model = useMemo(() => mobileCostModel(REPORT_INPUTS, policy), [policy]);
  const selected = agents.find((agent) => agent.id === selectedId) || agents[0];
  const visible = agents.filter((agent) => filter === "all" || agent.mobility === filter);

  // Live load: open tickets at each agent's stage, and its latest real output.
  const openAt = (agent) => records.filter((record) => record.current_stage === agent.stage && ["running", "waiting_for_review"].includes(record.status));
  const latestOutput = records.map((record) => record.agent_outputs?.[selected.stage]).find((output) => output && (!output.agent || stageOfAgent(output.agent) === selected.stage));
  const components = latestOutput?.components && selected.stage ? latestOutput.components : selected.components;

  /**
   * Send Scout-Log to all six nodes at once; each node animates as soon as it answers.
   * In-process nodes answer within milliseconds, so an answer is shown only after its bundle
   * has visibly arrived (no waiting with reduced motion).
   */
  async function investigate() {
    setInvestigating(true);
    setTripMode("mobile");
    const started = performance.now();
    const nodes = NODE_SERVICES.map((service, index) => ({ node_id: `node-${index + 1}`, service, mode: "mobile_agent", status: "travelling", logBytes: 0, bytesSent: 0, bytesReturned: 0, aggregate: null, error: null }));
    setLiveTrip({ source: "live", nodes });
    const settle = async (index, result) => {
      const arrival = reduced ? 0 : BUNDLE_TRAVEL_MS + index * 80;
      await new Promise((resolve) => window.setTimeout(resolve, Math.max(0, arrival - (performance.now() - started))));
      setLiveTrip((trip) => {
        const node = tripFromMigrations([result]).nodes[0];
        return { ...trip, nodes: trip.nodes.map((item, position) => (position === index ? { ...node, node_id: item.node_id, service: node.service === "unknown" ? item.service : node.service } : item)) };
      });
    };
    await Promise.allSettled(
      nodes.map((_, index) =>
        api.migrate(index + 1).then(
          (value) => settle(index, { status: "fulfilled", value }),
          (reason) => settle(index, { status: "rejected", reason }),
        ),
      ),
    );
    setInvestigating(false);
  }

  const nodesSimulated = health?.nodes?.kind && health.nodes.kind !== "http";
  const trip = liveTrip || modelTrip(model);

  return (
    <div className="page">
      <Heading
        eyebrow="Agents"
        title="Who does what?"
        what="The eleven agents: their family, whether they move (mobile) or stay (static), their live load and the five components each one runs."
        why="Specialist agents make each decision explainable, and the mobile Scout-Log keeps raw data on the data nodes."
      />
      <div className="fact-row">
        {Object.entries(families).map(([family, description]) => (
          <Panel key={family} className="fact">
            <Bot size={18} aria-hidden="true" />
            <div>
              <b>{family}</b>
              <small>{description}</small>
            </div>
          </Panel>
        ))}
      </div>

      <div className="split split-agents">
        <Panel className="list-panel">
          <SectionTitle
            title="The team"
            level={3}
            action={
              <div className="segmented" role="group" aria-label="Filter agents">
                {[
                  ["all", "All"],
                  ["STATIC", "Static"],
                  ["MOBILE", "Mobile"],
                ].map(([value, label]) => (
                  <button key={value} type="button" className={`segment ${filter === value ? "is-selected" : ""}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>
                    {label}
                  </button>
                ))}
              </div>
            }
          />
          <ul className="plain-list agent-list">
            {visible.map((agent) => {
              const load = agent.stage ? openAt(agent).length : null;
              return (
                <li key={agent.id}>
                  <button type="button" className={`list-button ${agent.id === selected.id ? "is-selected" : ""}`} aria-pressed={agent.id === selected.id} onClick={() => setSelectedId(agent.id)}>
                    <span className={`agent-avatar family-${agent.family.toLowerCase()}`} aria-hidden="true">
                      {agent.mobility === "MOBILE" ? <Smartphone size={17} /> : <Bot size={17} />}
                    </span>
                    <span>
                      <b>{agent.id}</b>
                      <small>{agent.purpose}</small>
                    </span>
                    <span className="agent-meta">
                      <Tag tone={agent.mobility === "MOBILE" ? "violet" : "neutral"} icon={agent.mobility === "MOBILE" ? Smartphone : MapPin}>
                        {agent.mobility === "MOBILE" ? "Mobile" : "Static"}
                      </Tag>
                      {load !== null && mode === "live" && <small>{load} open</small>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel className="detail-panel">
          <p className="eyebrow">
            {selected.family} · {families[selected.family]}
          </p>
          <h2>{selected.id}</h2>
          <p>{selected.purpose}</p>
          <ul className="chip-list">
            <li>
              <Tag tone={selected.mobility === "MOBILE" ? "violet" : "neutral"} icon={selected.mobility === "MOBILE" ? Smartphone : MapPin}>
                {selected.mobility === "MOBILE" ? "Mobile: moves to the data" : "Static: stays in one place"}
              </Tag>
            </li>
            <li>
              <Tag tone={SIMULATED_TAG[String(selected.simulated)].tone}>{SIMULATED_TAG[String(selected.simulated)].label}</Tag>
            </li>
            {selected.stage && (
              <li>
                <Tag>Stage: {stageInfo(selected.stage).name}</Tag>
              </li>
            )}
          </ul>
          {selected.squads && (
            <p className="muted small">
              Three squads bid for each ticket in a <Term id="contract-net">Contract Net</Term> auction: {selected.squads.map(shortAgentName).join(", ")}.
            </p>
          )}
          <h3 className="subhead">
            <Term id="five-components">Five components</Term> <span className="muted">{latestOutput?.components ? "(latest real run)" : "(as designed)"}</span>
          </h3>
          <ol className="components">
            {COMPONENTS.map((key) => (
              <li key={key}>
                <b>{key[0].toUpperCase() + key.slice(1)}</b>
                <span>{components?.[key] || <span className="muted">Not recorded</span>}</span>
              </li>
            ))}
          </ol>
          {selected.stage && mode === "live" && (
            <>
              <h3 className="subhead">Tickets at this stage now</h3>
              {openAt(selected).length ? (
                <ul className="plain-list">
                  {openAt(selected).map((record) => (
                    <li key={record.ticket_id}>
                      <code>{record.ticket_id}</code> {record.title}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">None right now.</p>
              )}
            </>
          )}
        </Panel>
      </div>

      <Panel>
        <SectionTitle
          title="The mobile agent at work"
          detail="Scout-Log visits the six data nodes of the flash-sale incident. Compare it with pulling every raw log to one server (report T36)."
        />
        <MobileAgentMap
          trip={liveTrip && tripMode === "mobile" ? trip : modelTrip(model)}
          model={model}
          source={liveTrip && tripMode === "mobile" ? "live" : "model"}
          mode={tripMode}
          onModeChange={(value) => {
            setTripMode(value);
            if (value === "static") setLiveTrip(null);
          }}
          onInvestigate={mode === "live" ? investigate : undefined}
          investigating={investigating}
          title={liveTrip && tripMode === "mobile" ? `Live trip${nodesSimulated ? " (in-process nodes)" : ""}` : "Report cost model: TCK-1042"}
        />
        {mode !== "live" && <p className="muted small">The real trip needs the backend; this is the report's cost model, played as an animation.</p>}
        <p className="muted small">
          Experiment results show A3 (mobile) sending <i>more</i> bytes than A2 on the tiny synthetic logs. That fits the <Term id="break-even">break-even</Term>: moving the agent only pays off
          when a node holds more than about {model.breakEvenMb} MB.
        </p>
      </Panel>
    </div>
  );
}
