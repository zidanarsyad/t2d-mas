export const stages = ["Intake", "Triage", "Assignment", "Investigation", "Planning", "Implementation", "QA", "Deployment", "Monitoring"];

export const seedTickets = [
  { id:"TCK-1042", title:"Checkout crashes during flash sale", severity:"Critical", agent:"Broker-Triage", stage:"Triage", age:"18m", waiting:true, component:"Payments API" },
  { id:"TCK-1038", title:"Payment retries create duplicate orders", severity:"High", agent:"Worker-Investigate", stage:"Investigation", age:"42m", component:"Orders" },
  { id:"TCK-1035", title:"Search results timeout for long queries", severity:"High", agent:"Worker-Plan", stage:"Planning", age:"1h 12m", component:"Search" },
  { id:"TCK-1031", title:"Session refresh returns an empty token", severity:"Medium", agent:"Worker-Impl", stage:"Implementation", age:"26m", component:"Identity" },
  { id:"TCK-1029", title:"Receipt view clips on small screens", severity:"Low", agent:"Worker-QA", stage:"QA", age:"9m", component:"Mobile app" },
  { id:"TCK-1026", title:"Inventory cache misses after warm restart", severity:"Medium", agent:"Worker-Deploy", stage:"Deployment", age:"14m", component:"Inventory" },
  { id:"TCK-1022", title:"Webhook delivery exceeds SLO", severity:"High", agent:"Scout-Monitor", stage:"Monitoring", age:"31m", component:"Integrations" },
  { id:"TCK-1018", title:"CSV export uses stale account name", severity:"Low", agent:"Scout-Feedback", stage:"Intake", age:"3m", component:"Accounts" },
  { id:"TCK-1014", title:"Invoice total differs by one cent", severity:"Medium", agent:"Broker-Assign", stage:"Assignment", age:"16m", component:"Billing" },
  { id:"TCK-1010", title:"Circuit breaker ignores recovery signal", severity:"Critical", agent:"Worker-Impl", stage:"Implementation", age:"1h 05m", waiting:true, component:"Payments API" },
  { id:"TCK-1008", title:"Gateway sees intermittent upstream reset", severity:"High", agent:"Scout-Log", stage:"Investigation", age:"22m", component:"API Gateway" },
  { id:"TCK-1002", title:"Role editor hides validation message", severity:"Low", agent:"Worker-QA", stage:"QA", age:"7m", component:"Admin UI" },
];

export const agents = [
  {id:"Scout-Feedback",role:"Scout",mode:"STATIC",host:"orchestrator-01",status:"Working",load:42,beat:"2s ago",task:"Normalizing crash reports"},
  {id:"Broker-Triage",role:"Broker",mode:"STATIC",host:"orchestrator-01",status:"Needs review",load:68,beat:"4s ago",task:"Severity and duplicate check"},
  {id:"Broker-Assign",role:"Broker",mode:"STATIC",host:"orchestrator-01",status:"Idle",load:21,beat:"5s ago",task:"Worker allocation"},
  {id:"Scout-Log",role:"Scout",mode:"MOBILE",host:"node-3",status:"Migrated",load:56,beat:"3s ago",task:"Aggregating local telemetry",bytes:"84 MB",route:["orchestrator","node-3","orchestrator"]},
  {id:"Worker-Investigate",role:"Worker",mode:"STATIC",host:"worker-02",status:"Working",load:74,beat:"1s ago",task:"Ranking service suspects"},
  {id:"Worker-Plan",role:"Worker",mode:"STATIC",host:"worker-01",status:"Idle",load:18,beat:"6s ago",task:"Acceptance criteria"},
  {id:"Worker-Impl",role:"Worker",mode:"MOBILE",host:"sandbox-4",status:"Working",load:63,beat:"2s ago",task:"Drafting isolated patch",bytes:"12.4 MB",route:["orchestrator","sandbox-4"]},
  {id:"Worker-QA",role:"Worker",mode:"STATIC",host:"ci-runner-02",status:"Working",load:81,beat:"1s ago",task:"Prioritizing regression tests"},
  {id:"Worker-Deploy",role:"Worker",mode:"STATIC",host:"release-01",status:"Canary",load:35,beat:"3s ago",task:"Watching 5% canary"},
  {id:"Scout-Monitor",role:"Scout",mode:"MOBILE",host:"node-5",status:"Monitoring",load:27,beat:"2s ago",task:"Checking service SLOs",bytes:"6.2 MB",route:["orchestrator","node-5"]},
  {id:"Security-Policy",role:"Security",mode:"STATIC",host:"policy-01",status:"Watching",load:12,beat:"1s ago",task:"Policy gate active"},
];

export const approvals = [
  {id:"APR-208",ticket:"TCK-1042",severity:"Critical",title:"Confirm flash-sale incident severity",agent:"Broker-Triage",waiting:"1h 10m",risk:.94,confidence:.88,evidence:"EVD-771 · payment-db saturation",why:"Critical risk exceeds Rmax (1.0 > 0.60). The classifier is confident, but this decision requires review."},
  {id:"APR-207",ticket:"TCK-1010",severity:"Critical",title:"Review circuit-breaker patch before merge",agent:"Worker-Impl",waiting:"38m",risk:.88,confidence:.91,evidence:"PR-441 · diff and test report",why:"Production merge always requires human review, independent of model confidence."},
  {id:"APR-205",ticket:"TCK-0994",severity:"High",title:"Approve release window exception",agent:"Worker-Deploy",waiting:"2h 04m",risk:.72,confidence:.66,evidence:"EVD-748 · SLO burn-rate snapshot",why:"Confidence is below tau. Deployment is paused until a reviewer decides."},
];

export const trace = [
 {time:"20:05:11",agent:"Scout-Feedback",kind:"Ticket intake",summary:"2,143 crash reports grouped into parent TCK-1042",input:"Crash reporter · Android 14 · version 4.18.2",output:"1 parent, 2,142 related reports",confidence:.99,gate:"Autonomous",approver:"—",policy:"τ 0.70 · Rmax 0.60",evidence:"Masked report bundle · 3 attachments"},
 {time:"20:17:00",agent:"Broker-Triage",kind:"Duplicate search",summary:"Related ticket TCK-0987 found at cosine 0.91",input:"Normalized title and description embedding",output:"Related, not duplicate: traffic context differs",confidence:.91,gate:"Autonomous",approver:"—",policy:"τdup 0.85 · review band 0.70–0.84",evidence:"TCK-0987 summary · similarity features"},
 {time:"20:25:00",agent:"Broker-Triage",kind:"Severity decision",summary:"Critical predicted with probability 0.88",input:"Checkout reports and affected-user estimate",output:"Critical · risk 1.00 exceeds Rmax",confidence:.88,gate:"Escalated",approver:"Incident commander · 21:30",policy:"τ 0.70 · Rmax 0.60",evidence:"Classifier probabilities · masked excerpt"},
 {time:"21:35:00",agent:"Broker-Assign",kind:"Contract Net",summary:"Worker W2 selected from three proposals",input:"Backend task · skill, load, normalized cost",output:"Utility 0.69 · W1 0.63 · W3 0.66",confidence:.97,gate:"Autonomous",approver:"—",policy:"U = 0.5 skill + 0.3 (1−load) + 0.2 (1−cost)",evidence:"Three normalized worker proposals"},
 {time:"22:05:00",agent:"Worker-Investigate",kind:"Root-cause ranking",summary:"payment-db ranked lead suspect (score 2.60)",input:"Aggregated trace, latency, and saturation features",output:"Connection-pool exhaustion hypothesis",confidence:.82,gate:"Autonomous",approver:"—",policy:"τ 0.70 · Rmax 0.60",evidence:"Top-3 ranking · aggregate metrics only"},
 {time:"23:15:00",agent:"Worker-QA",kind:"Test selection",summary:"120 of 3,400 tests passed within the 8-minute budget",input:"Diff proximity, historical failures, duration",output:"NAPFD 0.94 · 0 failures",confidence:.94,gate:"Autonomous",approver:"—",policy:"CI budget 8m · seed 42",evidence:"Test run TR-882 · aggregate report"},
];

// Fixed seed-like arithmetic keeps the report line chart reproducible in demo mode.
export const trend = Array.from({length:30},(_,i)=>({day:`Sep ${i+1}`,deploys:5+((i*7)%8)+Math.floor(i/8),lead:5.8-i*.073+((i%5)-2)*.13,failure:Math.max(1.8,7.6-i*.14+((i%6)-3)*.23)}));
