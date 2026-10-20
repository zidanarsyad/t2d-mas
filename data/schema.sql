-- PostgreSQL schema for the T2D-MAS course prototype: the agents' shared "blackboard".
-- Docker Compose runs this file once, when the database volume is first created.
-- After changing it, recreate the volume with `docker compose down -v`.
-- Manual use: psql "$DATABASE_URL" -f data/schema.sql
--
-- Tables: tickets (inputs), audit_log (every agent action, append-only),
-- code_changes and deployments (the two irreversible actions, guarded below),
-- policies (thresholds) and slo_baselines (what "healthy" means for monitoring).
-- The orchestrator seeds policies and slo_baselines from code at startup.

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
    -- Filled for tickets created through the dashboard (the data loaders leave them empty).
    status TEXT,
    language TEXT,
    app_version TEXT,
    platform TEXT,
    parent_ticket_id TEXT,
    created_on TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_on TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_severity ON tickets(severity);

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
CREATE INDEX IF NOT EXISTS idx_audit_log_ticket ON audit_log(ticket_id, occurred_at);

-- Rule 2: the audit log is append-only (no UPDATE, DELETE or TRUNCATE).
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
DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;
CREATE TRIGGER audit_log_no_truncate
BEFORE TRUNCATE ON audit_log
FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_log_mutation();

-- Draft pull requests written by Worker-Impl; merged only after the pr_merge review.
CREATE TABLE IF NOT EXISTS code_changes (
    change_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    repository TEXT NOT NULL,
    branch_name TEXT,
    title TEXT,
    diff_summary TEXT,
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    tests_added JSONB NOT NULL DEFAULT '[]'::jsonb,
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    merged BOOLEAN NOT NULL DEFAULT FALSE,
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at TIMESTAMPTZ,
    CHECK (NOT merged OR human_approved)
);

-- Canary and production releases written by Worker-Deploy.
-- A 5% canary may run on its own for low-risk releases; production needs a sign-off.
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL REFERENCES code_changes(change_id),
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    environment TEXT NOT NULL CHECK (environment IN ('canary', 'production')),
    strategy TEXT NOT NULL,
    risk_score REAL,
    status TEXT NOT NULL CHECK (status IN ('canary_passed', 'rolled_back', 'deployed')),
    human_approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by TEXT,
    slo_breach BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployed_at TIMESTAMPTZ,
    rollback_of TEXT REFERENCES deployments(deployment_id),
    CHECK (status <> 'deployed' OR human_approved)
);

-- Rule 1, enforced again in the database: no merge or full deploy without human_approved.
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
    IF NEW.status = 'deployed' AND NOT NEW.human_approved THEN
        RAISE EXCEPTION 'deployment requires human_approved = TRUE';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS deployments_require_approval ON deployments;
CREATE TRIGGER deployments_require_approval
BEFORE INSERT OR UPDATE ON deployments
FOR EACH ROW EXECUTE FUNCTION require_human_approval_for_deploy();

-- Autonomy thresholds (tau, R_max) plus the other rules as JSON (see agents/policy.py).
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tau REAL NOT NULL CHECK (tau BETWEEN 0 AND 1),
    risk_max REAL NOT NULL CHECK (risk_max BETWEEN 0 AND 1),
    rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- What "healthy" looks like per service and metric; Scout-Monitor compares against it.
CREATE TABLE IF NOT EXISTS slo_baselines (
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    window_minutes INTEGER NOT NULL,
    baseline_mean DOUBLE PRECISION NOT NULL,
    baseline_std DOUBLE PRECISION NOT NULL,
    slo_threshold DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (service, metric)
);
