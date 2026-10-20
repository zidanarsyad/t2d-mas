// One stage's result: the agent's five components, its gate decisions, the stage-specific
// highlights a reviewer cares about, and the raw output on demand.
import { CircleCheck, CircleX, ShieldCheck, ShieldAlert } from "lucide-react";
import { agentInfo } from "../data/agents.js";
import { formatBytes, formatNumber, formatTime } from "../lib/format.js";
import { DEFAULT_POLICY, duplicateBandLabel, gateLabel, gateReasonLabel } from "../lib/policy.js";
import { languageLabel } from "../lib/feedback.js";
import { metricInfo } from "../lib/telemetry.js";
import { shortAgentName, stageInfo } from "../lib/workflow.js";
import BidTable from "./BidTable";
import OutputSummary from "./OutputSummary";
import Term from "./Term";
import { Severity, SourceBadge, Tag } from "./Primitives";

const COMPONENTS = [
  ["perceive", "Perceive"],
  ["remember", "Remember"],
  ["reason", "Reason"],
  ["act", "Act"],
  ["report", "Report"],
];

const MODE_SOURCE = { live: "live", simulated: "simulated", mixed: "simulated" };

function Fact({ label, children }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children ?? <span className="muted">Not recorded</span>}</dd>
    </div>
  );
}

function Decision({ item, policy }) {
  const inputs = item.inputs || {};
  const Icon = item.autonomous ? ShieldCheck : ShieldAlert;
  const numbers = Object.entries(inputs)
    .filter(([, value]) => typeof value === "number")
    .map(([key, value]) => `${key.replaceAll("_", " ")} ${formatNumber(value, 2)}`)
    .join(" · ");
  return (
    <li className={item.autonomous ? "is-autonomous" : "is-human"}>
      <Icon size={16} aria-hidden="true" />
      <span>
        <b>{gateLabel(item.gate, policy)}:</b> {item.autonomous ? "the agent may continue" : "a person decides"}
        {item.reason && <> — {gateReasonLabel[item.reason] || String(item.reason).replaceAll("_", " ")}</>}
        {numbers && <small className="decision-inputs">{numbers}</small>}
      </span>
    </li>
  );
}

function Highlights({ stage, output, policy }) {
  if (stage === "intake")
    return (
      <dl className="facts">
        <Fact label="Language">{output.language ? languageLabel(output.language) : null}</Fact>
        <Fact label="Component">{output.component ? `${output.component}${output.component_confidence !== undefined ? ` (${formatNumber(output.component_confidence, 2)})` : ""}` : null}</Fact>
        <Fact label="App version / platform">{[output.app_version, output.platform, output.device].filter(Boolean).join(" · ") || null}</Fact>
        <Fact label="Personal data masked">{output.pii_masked ? Object.entries(output.pii_masked).map(([key, value]) => `${value} ${key}`).join(", ") : null}</Fact>
        {output.reproduction_hints?.length > 0 && <Fact label="Steps to reproduce">{output.reproduction_hints.join(" → ")}</Fact>}
      </dl>
    );
  if (stage === "triage") {
    const duplicate = output.duplicate;
    return (
      <dl className="facts">
        <Fact label="Severity">
          <Severity value={output.severity} />
        </Fact>
        <Fact label={<Term id="tau">Confidence</Term>}>{output.confidence !== undefined ? formatNumber(output.confidence, 2) : null}</Fact>
        <Fact label={<Term id="duplicate-bands">Duplicate check</Term>}>
          {duplicate ? (
            <>
              {duplicateBandLabel[duplicate.band] || duplicate.band}
              {duplicate.best_match?.ticket_id && ` · closest ${duplicate.best_match.ticket_id} (${formatNumber(duplicate.best_match.cosine, 2)})`}
            </>
          ) : null}
        </Fact>
        {output.matched_cues?.length > 0 && <Fact label="Words that mattered">{output.matched_cues.join(", ")}</Fact>}
        {output.rationale && <Fact label="Why">{output.rationale}</Fact>}
      </dl>
    );
  }
  if (stage === "assignment")
    return (
      <>
        <BidTable bids={output.bids} winner={output.winner} />
        <dl className="facts">
          <Fact label="Winner">{output.squad ? `${output.squad} squad` : output.winner ? shortAgentName(output.winner) : null}</Fact>
          <Fact label="SLA">{output.sla_hours ? `${output.sla_hours} h${output.sla_due ? `, due ${formatTime(output.sla_due, { date: true, seconds: false })}` : ""}` : null}</Fact>
        </dl>
      </>
    );
  if (stage === "investigation")
    return (
      <dl className="facts">
        <Fact label="Investigator">{output.investigator ? shortAgentName(output.investigator) : null}</Fact>
        <Fact label="Data moved">{output.bytes_moved !== undefined ? `${formatBytes(output.bytes_moved)} (raw logs kept on nodes: ${formatBytes(output.raw_log_bytes_kept_on_nodes)})` : null}</Fact>
        <Fact label="Suspects (ranked)">{output.rca?.ranking?.length ? output.rca.ranking.slice(0, 3).map((item) => `${item.service} ${formatNumber(item.score, 2)}`).join(" · ") : null}</Fact>
        <Fact label="Hypothesis">{output.hypothesis}</Fact>
        <Fact label="Root cause confirmed">{output.root_cause_confirmed === false ? "No — this is a hypothesis to verify" : output.root_cause_confirmed ? "Yes" : null}</Fact>
      </dl>
    );
  if (stage === "planning")
    return (
      <div className="stack">
        {output.subtasks?.length > 0 && (
          <ol className="plain-numbered">
            {output.subtasks.map((task, index) => (
              <li key={task.id || index}>
                {typeof task === "string" ? task : `${task.title}${task.estimate_hours ? ` (${task.estimate_hours} h)` : ""}`}
              </li>
            ))}
          </ol>
        )}
        {output.acceptance_criteria?.length > 0 && (
          <ul className="criteria">
            {output.acceptance_criteria.map((item, index) =>
              typeof item === "string" ? (
                <li key={index}>{item}</li>
              ) : (
                <li key={index}>
                  <b>Given</b> {item.given}, <b>when</b> {item.when}, <b>then</b> {item.then}.
                </li>
              ),
            )}
          </ul>
        )}
      </div>
    );
  if (stage === "implementation") {
    const pr = output.draft_pr;
    const scan = output.security_precheck;
    return (
      <dl className="facts">
        <Fact label="Draft pull request">{pr ? `${pr.title || pr.change_id} (${pr.branch || "branch"})` : null}</Fact>
        <Fact label="Size">{pr?.diff_stats ? `${pr.diff_stats.files} files, +${pr.diff_stats.additions} / −${pr.diff_stats.deletions}` : null}</Fact>
        <Fact label="Secret scan">
          {scan ? (
            <span className={scan.passed ? "text-ok" : "text-bad"}>
              {scan.passed ? <CircleCheck size={14} aria-hidden="true" /> : <CircleX size={14} aria-hidden="true" />} {scan.passed ? "No secrets found" : `${scan.findings?.length || 1} secret(s) found`}
            </span>
          ) : null}
        </Fact>
        <Fact label="Repository changed">{output.repository_modified === false ? "No (simulated draft only)" : null}</Fact>
      </dl>
    );
  }
  if (stage === "qa")
    return (
      <dl className="facts">
        <Fact label="Tests selected">{output.selected_tests !== undefined ? `${formatNumber(output.selected_tests)} of ${formatNumber(output.suite_size)} (${output.duration_minutes} of ${output.budget_minutes ?? policy.ci.budget_minutes} min)` : null}</Fact>
        <Fact label={<Term id="napfd">NAPFD</Term>}>{output.napfd !== undefined ? formatNumber(output.napfd, 2) : null}</Fact>
        <Fact label="Result">{output.passed !== undefined ? `${formatNumber(output.passed)} passed, ${formatNumber(output.failed)} failed${output.flaky_retried ? `, ${output.flaky_retried} flaky retried` : ""}` : output.pass_fail}</Fact>
      </dl>
    );
  if (stage === "deployment")
    return (
      <dl className="facts">
        <Fact label={<Term id="risk-score">Release risk score</Term>}>{output.risk_score !== undefined ? formatNumber(output.risk_score, 2) : null}</Fact>
        <Fact label={<Term id="canary">Canary</Term>}>{output.canary ? `${output.canary.percent}% · ${String(output.canary.status).replaceAll("_", " ")}` : null}</Fact>
        <Fact label="Full release">{output.full_release ? String(output.full_release.status).replaceAll("_", " ") : null}</Fact>
      </dl>
    );
  if (stage === "monitoring")
    return (
      <dl className="facts">
        <Fact label="Signals">
          {output.signals?.length
            ? output.signals.map((signal) => `${metricInfo(signal.metric).label} ${metricInfo(signal.metric).format(signal.value)} (z ${formatNumber(signal.z, 1)}${signal.breach ? ", breaks the SLO" : ""})`).join(" · ")
            : null}
        </Fact>
        <Fact label="Follow-up ticket">{output.follow_up_ticket_id || (output.anomalies?.length === 0 ? "None needed" : null)}</Fact>
        <Fact label="Baseline updated">{output.baseline_updated === undefined ? null : output.baseline_updated ? "Yes" : "No"}</Fact>
      </dl>
    );
  return null;
}

export default function StageDetails({ record, stageId, policy = DEFAULT_POLICY }) {
  const stage = stageInfo(stageId);
  const output = record?.agent_outputs?.[stageId];
  const design = agentInfo(output?.agent || stage.agent);
  const components = output?.components || design?.components || {};
  return (
    <div className="stage-details">
      <div className="stage-details-head">
        <div>
          <h3>{stage.name}</h3>
          <p className="muted">
            {shortAgentName(output?.agent || stage.agent)} · {stage.plain}
          </p>
        </div>
        {output ? (
          <SourceBadge source={MODE_SOURCE[output.execution_mode] || "live"} label={output.execution_mode === "mixed" ? "Mixed: real + simulated" : undefined} />
        ) : (
          <Tag>Not run yet</Tag>
        )}
      </div>
      {output?.summary && <p className="stage-summary">{output.summary}</p>}
      {output?.simulation_note && <p className="muted small">{output.simulation_note}</p>}
      {!output && <p className="muted">{stage.description}</p>}

      <h4 className="subhead">
        <Term id="five-components">Five components</Term> {!output?.components && <span className="muted">(as designed)</span>}
      </h4>
      <ol className="components">
        {COMPONENTS.map(([key, label]) => (
          <li key={key}>
            <b>{label}</b>
            <span>{components[key] || <span className="muted">Not recorded</span>}</span>
          </li>
        ))}
      </ol>

      {output?.decisions?.length > 0 && (
        <>
          <h4 className="subhead">Gate checks</h4>
          <ul className="decision-list">
            {output.decisions.map((item, index) => (
              <Decision key={`${item.gate}-${index}`} item={item} policy={policy} />
            ))}
          </ul>
        </>
      )}

      {output && (
        <>
          <h4 className="subhead">Highlights</h4>
          <Highlights stage={stageId} output={output} policy={policy} />
        </>
      )}

      {output?.tools_used?.length > 0 && (
        <details className="details">
          <summary>Tools used ({output.tools_used.length})</summary>
          <ul className="tool-list">
            {output.tools_used.map((tool, index) => (
              <li key={`${tool.tool}-${index}`}>
                <code>{tool.tool}</code> {tool.simulated ? <Tag tone="amber">simulated</Tag> : <Tag tone="green">real</Tag>} {tool.detail}
              </li>
            ))}
          </ul>
        </details>
      )}
      {output && <OutputSummary output={output} />}
    </div>
  );
}
