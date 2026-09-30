// Designed agent roles. Runtime health is not fabricated by this catalog.
export const agents = [
  { id: "Scout-Feedback", role: "Scout", mode: "STATIC" },
  { id: "Broker-Triage", role: "Broker", mode: "STATIC" },
  { id: "Broker-Assign", role: "Broker", mode: "STATIC" },
  { id: "Scout-Log", role: "Scout", mode: "MOBILE" },
  { id: "Worker-Investigate", role: "Worker", mode: "STATIC" },
  { id: "Worker-Plan", role: "Worker", mode: "STATIC" },
  { id: "Worker-Impl", role: "Worker", mode: "MOBILE" },
  { id: "Worker-QA", role: "Worker", mode: "STATIC" },
  { id: "Worker-Deploy", role: "Worker", mode: "STATIC" },
  { id: "Scout-Monitor", role: "Scout", mode: "MOBILE" },
  { id: "Security-Policy", role: "Security", mode: "STATIC" },
];

// Deterministic illustrative performance series; it is not operational telemetry.
export const trend = Array.from({ length: 30 }, (_, i) => ({
  day: `Sep ${i + 1}`,
  deploys: 5 + ((i * 7) % 8) + Math.floor(i / 8),
  lead: 5.8 - i * 0.073 + ((i % 5) - 2) * 0.13,
  failure: Math.max(1.8, 7.6 - i * 0.14 + ((i % 6) - 3) * 0.23),
}));
