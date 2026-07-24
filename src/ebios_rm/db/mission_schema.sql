-- Mission database — continuous read-write, multi-mission (conception §12, §12.6).

CREATE TABLE IF NOT EXISTS missions (
    mission_id                       TEXT PRIMARY KEY,
    name                             TEXT NOT NULL,
    status                           TEXT NOT NULL,
    created_at                       TEXT NOT NULL,
    updated_at                       TEXT NOT NULL,
    attck_version_used               TEXT,            -- filled by workshop 2+, NULL during workshop 1
    compliance_frameworks_declared   TEXT NOT NULL,   -- JSON list
    compliance_frameworks_versions   TEXT,            -- JSON object, framework -> version
    restart_from                     TEXT
);

-- workshop_number 0 = the Mission Context (intake result); 1..5 = each atelier's output.
CREATE TABLE IF NOT EXISTS workshop_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      TEXT NOT NULL REFERENCES missions(mission_id),
    workshop_number INTEGER NOT NULL,
    version_number  INTEGER NOT NULL,
    output          TEXT NOT NULL,   -- JSON
    status          TEXT NOT NULL,   -- current | approved | superseded | rejected
    created_at      TEXT NOT NULL
);
-- Rollback cap (conception §12.6): count rows for a given mission_id/workshop_number,
-- no separate counter column needed. Hard cap at 3 before reinforced confirmation.

CREATE TABLE IF NOT EXISTS decision_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          TEXT NOT NULL REFERENCES missions(mission_id),
    stage               TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    decided_by          TEXT NOT NULL,
    action_taken        TEXT NOT NULL,
    justification_given TEXT NOT NULL,   -- non-empty, universal rule (§8)
    estimated_cost_usd  REAL,
    actual_cost_usd     REAL
);

CREATE TABLE IF NOT EXISTS cost_calibration_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id         TEXT,
    input_tokens       INTEGER NOT NULL,
    output_tokens      INTEGER NOT NULL,
    tool_calls         INTEGER NOT NULL,
    wall_clock_seconds REAL NOT NULL,
    model_used         TEXT NOT NULL,
    logged_at          TEXT NOT NULL
);
