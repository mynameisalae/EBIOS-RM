-- Reference database — read-only during a mission, refreshed periodically,
-- version pinned per mission (conception §12, §12.1, §12.3).

CREATE TABLE IF NOT EXISTS attack_techniques (
    technique_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    tactic          TEXT NOT NULL,
    description     TEXT NOT NULL,
    attck_version   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_mitigations (
    mitigation_id           TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    description             TEXT NOT NULL,
    applies_to_technique_id TEXT NOT NULL REFERENCES attack_techniques(technique_id)
);

CREATE TABLE IF NOT EXISTS attack_groups (
    group_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sectors     TEXT NOT NULL,   -- JSON list
    motivations TEXT NOT NULL    -- JSON list
);

-- Populated by framework plugins (src/ebios_rm/plugins/frameworks/*), never
-- hardcoded per referential — see plugins/registry.py and db/loader.py.
CREATE TABLE IF NOT EXISTS baseline_controls (
    control_id            TEXT PRIMARY KEY,
    framework             TEXT NOT NULL,   -- discriminant, e.g. 'ISO27001', 'RGPD'
    description           TEXT NOT NULL,   -- real referential text
    category              TEXT NOT NULL,
    covers_risk_category  TEXT NOT NULL,   -- JSON list; empty if not relevant to workshop 4
    framework_version     TEXT NOT NULL,
    legal_impact_type     TEXT,            -- NULL | 'financial_penalty' | 'mandatory_notification' | 'liability' (§12.3)
    legal_impact_details  TEXT             -- real consequence text (penalty cap, notification delay, ...)
);
