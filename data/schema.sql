-- Minimal PostgreSQL schema for the T2D-MAS course prototype.
-- Run with: psql "$DATABASE_URL" -f data/schema.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    component TEXT,
    severity TEXT NOT NULL DEFAULT 'Unknown'
        CHECK (severity IN ('Critical', 'High', 'Medium', 'Low', 'Unknown')),
    created_at TIMESTAMPTZ,
    -- Kept as a plain ID because a parent duplicate may not be in a sampled export.
    duplicate_of TEXT,
    dataset_version TEXT NOT NULL,
    pii_masked BOOLEAN NOT NULL DEFAULT FALSE,
    created_on TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_severity ON tickets(severity);

CREATE TABLE IF NOT EXISTS ticket_embeddings (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding VECTOR(384),
    dataset_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    mobility TEXT NOT NULL DEFAULT 'STATIC' CHECK (mobility IN ('STATIC', 'MOBILE')),
    host TEXT,
    status TEXT NOT NULL DEFAULT 'idle',
    load REAL NOT NULL DEFAULT 0 CHECK (load BETWEEN 0 AND 1),
    heartbeat_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS messages (
    message_id BIGSERIAL PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    sender_id TEXT REFERENCES agents(agent_id),
    recipient_id TEXT REFERENCES agents(agent_id),
    performative TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id BIGSERIAL PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    summary TEXT NOT NULL,
    aggregate_features JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_data_location TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    agent_id TEXT REFERENCES agents(agent_id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    autonomy_probability REAL,
    risk REAL,
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS code_changes (
    change_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    repository TEXT NOT NULL,
    branch_name TEXT,
    commit_sha TEXT,
    diff_summary TEXT,
    merged BOOLEAN NOT NULL DEFAULT FALSE,
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT merged OR human_approved)
);

CREATE TABLE IF NOT EXISTS test_runs (
    test_run_id TEXT PRIMARY KEY,
    change_id TEXT REFERENCES code_changes(change_id),
    status TEXT NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL REFERENCES code_changes(change_id),
    environment TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    deployed_at TIMESTAMPTZ,
    rollback_of TEXT REFERENCES deployments(deployment_id),
    CHECK (status NOT IN ('deployed', 'succeeded') OR human_approved)
);

CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tau REAL NOT NULL CHECK (tau BETWEEN 0 AND 1),
    risk_max REAL NOT NULL CHECK (risk_max BETWEEN 0 AND 1),
    rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    correlation_id TEXT,
    actor_id TEXT,
    action TEXT NOT NULL,
    ticket_id TEXT,
    decision TEXT,
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only; % is not allowed', TG_OP;
END;
$$;
DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;
CREATE TRIGGER audit_log_no_update_delete
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();

CREATE TABLE IF NOT EXISTS slo_baselines (
    baseline_id TEXT PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    dataset_version TEXT NOT NULL,
    notes TEXT
);

-- Defense in depth for the two irreversible actions in this prototype.
CREATE OR REPLACE FUNCTION require_human_approval_for_merge()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.merged AND NOT NEW.human_approved THEN
        RAISE EXCEPTION 'merge requires human_approved = TRUE';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS code_changes_require_approval ON code_changes;
CREATE TRIGGER code_changes_require_approval
BEFORE INSERT OR UPDATE ON code_changes
FOR EACH ROW EXECUTE FUNCTION require_human_approval_for_merge();

CREATE OR REPLACE FUNCTION require_human_approval_for_deploy()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('deployed', 'succeeded') AND NOT NEW.human_approved THEN
        RAISE EXCEPTION 'deployment requires human_approved = TRUE';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS deployments_require_approval ON deployments;
CREATE TRIGGER deployments_require_approval
BEFORE INSERT OR UPDATE ON deployments
FOR EACH ROW EXECUTE FUNCTION require_human_approval_for_deploy();
