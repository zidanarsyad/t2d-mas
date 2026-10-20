import test from "node:test";
import assert from "node:assert/strict";
import { mobileCostModel, modelTrip, nodeFromMigrationEvent, REPORT_INPUTS, ringPositions, tripFromMigrations, tripFromSnapshot, tripSteps, tripTotals } from "./mobileTrip.js";

const model = mobileCostModel(REPORT_INPUTS);

test("the cost model reproduces the report's static vs mobile numbers", () => {
  assert.equal(model.static.mb, 8190);
  assert.equal(Math.round(model.static.seconds), 655);
  assert.equal(model.mobile.mb, 84);
  assert.equal(Math.round(model.mobile.seconds), 27);
  assert.equal(Number(model.savedPercent.toFixed(2)), 98.97);
  assert.equal(Math.floor(model.speedup), 24);
  assert.equal(model.breakEvenMb, 14);
  assert.equal(model.migrateThresholdMb, 42);
});

test("tripSteps end at the model totals", () => {
  const mobile = tripSteps(model, "mobile");
  assert.deepEqual(mobile.map((step) => step.id), ["sign", "dispatch", "execute", "return", "done"]);
  assert.equal(mobile.at(-1).counterMb, 84);
  assert.ok(Math.abs(mobile.at(-1).seconds - model.mobile.seconds) < 1e-9);
  mobile.slice(1).forEach((step, index) => assert.ok(step.counterMb >= mobile[index].counterMb));
  const stat = tripSteps(model, "static");
  assert.equal(stat.at(-1).counterMb, 8190);
});

test("ringPositions are equidistant from the centre and from each other", () => {
  const points = ringPositions(6, 300, 180, 120);
  points.forEach((point) => assert.ok(Math.abs(Math.hypot(point.x - 300, point.y - 180) - 120) < 0.01));
  const gaps = points.map((point, index) => {
    const next = points[(index + 1) % points.length];
    return Math.hypot(next.x - point.x, next.y - point.y);
  });
  gaps.forEach((gap) => assert.ok(Math.abs(gap - gaps[0]) < 0.01));
  assert.ok(Math.abs(points[0].x - 300) < 0.01 && points[0].y < 180);
});

test("tripFromMigrations keeps failed nodes and tripTotals adds up", () => {
  const visit = (index) => ({ node_id: `node-${index}`, service: "payment-db", mode: "mobile_agent", bytes_sent: 1000, bytes_returned: 200, migration_rule: { log_mb: 64, should_migrate: true }, aggregate: { error_rate: 0.1 }, error: null });
  const trip = tripFromMigrations([
    { status: "fulfilled", value: visit(1) },
    { status: "rejected", reason: new Error("node offline") },
  ]);
  assert.equal(trip.nodes[0].status, "returned");
  assert.equal(trip.nodes[1].status, "failed");
  assert.equal(trip.nodes[1].error, "node offline");
  const totals = tripTotals(trip);
  assert.equal(totals.bytesMoved, 1200);
  assert.equal(totals.bytesKept, 64e6);
  assert.equal(totals.failed, 1);
});

test("tripFromSnapshot reads node visits and model trips use the report sizes", () => {
  assert.equal(tripFromSnapshot({ agent_outputs: {} }), null);
  const trip = tripFromSnapshot({ ticket_id: "T-1", agent_outputs: { investigation: { node_visits: [{ node_id: "node-3", mode: "node_exporter", bytes_sent: 40, bytes_returned: 300, migration_rule: { log_mb: 20, should_migrate: false } }] } } });
  assert.equal(trip.nodes[0].shouldMigrate, false);
  assert.equal(trip.nodes[0].mode, "node_exporter");
  const totals = tripTotals(modelTrip(model));
  assert.equal(totals.bytesMoved, 84e6);
  assert.equal(totals.bytesKept, 8190e6);
});

test("an agent.migrated event becomes a returned trip node", () => {
  const node = nodeFromMigrationEvent({ node_id: "node-3", service: "payment-db", mode: "mobile_agent", should_migrate: true, log_bytes: 64e6, bytes_sent: 2110, bytes_returned: 150 });
  assert.equal(node.status, "returned");
  assert.equal(node.shouldMigrate, true);
  assert.equal(node.logBytes, 64e6);
  assert.equal(node.bytesSent + node.bytesReturned, 2260);
});
