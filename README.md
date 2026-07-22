# EBIOS RM Agent

AI-assisted agent for the EBIOS Risk Manager methodology. The system is
AI-**assisted**, never AI-**driven**: it extracts, proposes, flags
contradictions and gaps, and explains its reasoning — it never invents
information, never makes a final audit decision, and never resolves a
contradiction on its own. The auditor always has the last word.

The full design reference is [`docs/conception/CONCEPTION.md`](docs/conception/CONCEPTION.md) —
the single, authoritative source for every architectural decision in this
repository. This README only orients; when in doubt, the conception document wins.

## Stack

| Component | Choice | Role |
|---|---|---|
| Language | Python 3.13 | |
| Agent framework | Agno 2.6.x | Agents, orchestration, tools, HITL |
| Runtime | AgentOS | Execution server (FastAPI) |
| Database | SQLite (x2: reference + mission) | No vector store anywhere |
| Reporting | python-docx | Mission report + audit annex |
| Model provider | OpenRouter (sole provider) | `MODEL_ID` env var switches test/prod |
| Container | Docker, multi-stage, non-root | |

## Layout

```
src/ebios_rm/
  mission_context/   intake form, Fact model, 3-case validation, priority matrix
  orchestrator/       Workshop N -> Mission State -> Orchestrator -> N+1 (never direct calls)
  domain/             typed models shared across layers (Fact, EssentialAsset, ...)
  workshops/          the five ateliers, one agent (or fan-out) each
  services/           business-service layer — EBIOS RM logic
  repositories/       data access only, no business logic
  toolkits/           Agno toolkits — ATT&CK and compliance queries
  db/                 schemas + reference-db-loader (plugin-aware)
  plugins/frameworks/ one folder per law/standard — see below
  reporting/          mission report (LLM) + audit annex (pure data render)
```

## Standards and laws as plugins

Every compliance framework (ISO 27001, ANSSI hygiene, RGPD, NIST CSF, and any
future one — HIPAA, PCI-DSS, ...) lives in its own folder under
`src/ebios_rm/plugins/frameworks/<framework_id>/`, containing:

- `manifest.yaml` — id, display name, version, legal nature, whether it carries
  `legal_impact_type` provisions (conception §12.3)
- `controls.json` — rows matching the `baseline_controls` schema (conception §12.1)

The `reference-db-loader` service discovers every plugin folder at load time
and inserts its controls into the reference database — adding a new
standard never touches orchestrator, workshop, or agent code (conception §12.5).
See `src/ebios_rm/plugins/frameworks/_template/` as a starting point for a new one.

## Development

```bash
cp .env.example .env   # fill in OPENROUTER_API_KEY
pip install -r requirements-dev.txt
pytest
```
