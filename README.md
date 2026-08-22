# EBIOS RM Agent

AI-assisted agent for the EBIOS Risk Manager methodology. The system is
AI-**assisted**, never AI-**driven**: it extracts, proposes, flags
contradictions and gaps, and explains its reasoning — it never invents
information, never makes a final audit decision, and never resolves a
contradiction on its own. The auditor always has the last word.

The design reference is an internal document (`docs/conception/`, not published)
and remains the authoritative source for every architectural decision here — the
`§n` markers throughout the code point at its sections. This README only orients.

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

## Running Workshop 1 (no front end yet — CLI)

The audit contact fills the Word questionnaire
([`docs/intake/Questionnaire_Contexte_EBIOS_RM.docx`](docs/intake/Questionnaire_Contexte_EBIOS_RM.docx))
and returns it. You then run Workshop 1 against that file. Any format works —
`.docx`, `.pdf`, `.txt`, `.md` — the reader picks the method by extension; pass
the path as-is, no conversion needed (`.pdf` needs `pip install pdfplumber`).

Start a new mission (filled questionnaire, plus any optional supporting docs —
security policy, network diagram, prior report):

```bash
python scripts/run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]
```

It prints a `mission_id` at the top. What happens: the agent ingests the
document(s), asks follow-up questions for anything missing or thin, generates its
own expert audit questions, then runs the workshop and shows `w1_output`. During
the questions you can, at any prompt:

- **answer** it, or type a **question** (`c'est quoi un EDR ?`) — the agent
  explains and re-asks;
- **`skip`** an important question (a reason is required);
- **`!your text`** to force-record an answer verbatim when the agent keeps
  pushing back (you always outrank the agent);
- when it later asks *"Approuvez-vous ce résultat ?"*, answer `oui` / `non`
  (a rejection requires a reason).

### If you reject the result

Your reason is recorded in the decision log, then you choose:

- **`c` — correct it yourself.** Give the field path
  (`evenements_redoutes.0.gravite`), the new value, and a justification (required).
  No LLM call; the change is saved as a new version carrying an edit trail
  (what changed, from what, by whom, why) that the report will show.
- **`r` — let the agent redo it.** You pick *which parts* to regenerate —
  assets/feared events, baseline gaps, legal impacts, or all — and only those are
  re-run. The rest is kept **verbatim**, so rejecting a wrong gravité never
  reshuffles assets you were happy with. Your reason is passed to the agent as an
  explicit instruction, and reasons accumulate across attempts.
- **`q` — stop.** The last version is kept, stored as *not approved*.

Every attempt is its own version; nothing is overwritten, and only an approved
version counts as complete. After 3 versions the rollback cap (conception §12.6)
requires typing `CONFIRMER` to go further.

### Same weakness, several referentials

ISO 27001, NIST and ANSSI often demand the same thing, so one real weakness would
otherwise appear as three near-identical findings. Before the result is shown for
approval, the agent proposes which gaps describe **one** weakness; you confirm in
a single pass (`[Entrée]` accepts all, or name the groups to leave separate).

A confirmed group becomes one entry listing every control that requires the fix:

```
Pas de MFA sur les accès distants
   ISO27001       A.5.15
   NIST           PR.AA-05
   ANSSI_hygiene  ANSSI-H-21
```

Nothing is grouped automatically — a wrongly merged pair would silently drop a
finding (§15 step 9). Workshop 4 then analyses each weakness once instead of once
per referential.

### Controls the agent could not conclude on

A control the agent cannot settle is never quietly counted as compliant — it is
reported as **unverified, with the reason**, grouped so you can see at a glance
what kind of problem it is:

- *Information absente du contexte* — the client never said. A question for you.
- *Verdict rendu sans preuve citée* — the agent claimed something without citing a
  fact, so the code refused it. That points at the prompt, not at the client.
- *Contrôle inconnu du référentiel* / *Verdict non exploitable* — model malfunction.

You are **not** interrogated control by control: with hundreds of controls that
guarantees the list gets skipped and the audit trail fills with empty
justifications. You read the list and type a control id only for the ones you want
to document; the information is recorded in the decision log and the control stays
explicitly unverified until it is reassessed.

### Missing referential controls

If a declared framework has no controls loaded, the run **stops** before the
workshop: the agent must never invent referential text or assume coverage. Either
fill that plugin's `controls.json`, rebuild the reference DB and `--resume`, or
explicitly withdraw the framework with a reason (logged as a decision).

### Token usage

Every LLM call's tokens are recorded per mission.

```bash
python scripts/mission_tokens.py                 # all missions
python scripts/mission_tokens.py <mission_id>    # one mission, broken down by model
```

Cost is reported as `0`: only tokens are counted, no pricing table is baked in.

### Stop and continue later

Everything is saved to a SQLite file (`data/mission/mission.db` by default). You
can stop **any time** — even mid-question — and continue later: progress is saved
after every answer.

```bash
python scripts/run_workshop1_from_docs.py --list                 # saved missions + status
python scripts/run_workshop1_from_docs.py --resume <mission_id>  # continue where you left off
```

Resume skips whatever is already answered and picks up at the first unanswered
question; if the workshop already ran, it just shows the saved result.

> The data lives in that one `.db` file — back it up by copying it. In Docker it
> lives in the `mission_db_data` volume instead (same file, conception §13.3).
