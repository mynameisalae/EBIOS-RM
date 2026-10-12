# EBIOS RM Agent

An AI-assisted auditor's tool for the **EBIOS Risk Manager** method (ANSSI). It
conducts a risk study through the method's five workshops (*ateliers*), from the
client's questionnaire to a risk treatment plan the direction signs off.

The system is AI-**assisted**, never AI-**driven**. The agent reads, extracts,
proposes, flags and explains; it never invents a fact about the organisation, never
takes a methodological decision, and never approves its own work. **The auditor
always has the last word**, and every decision they take is logged with its reason.

---

## How the system works

### One study, five ateliers, in order

Each atelier starts only once the previous one is **approved** by the auditor, and
reads nothing but that approved result. Everything is stored per mission in one
SQLite file, so a study can span days.

| Atelier | Question it answers | What it produces | The agent… | The auditor… |
|---|---|---|---|---|
| **Intake** | What do we know about the organisation? | the *Mission Context*: every answer as a sourced fact | reads the questionnaire and documents, asks follow-ups, writes expert questions | answers, corrects, resolves contradictions |
| **1 — Cadrage et socle** | What must be protected, how badly would it hurt, and where does the security baseline fall short? | essential assets, support assets, feared events with their gravité, baseline gaps per standard | proposes assets and feared events, assesses each control of the declared standards against the facts | approves, corrects, groups duplicate gaps |
| **2 — Sources de risque** | Who could attack, and what would they be after? | risk sources, targeted objectives, rated SR/OV couples | proposes actors from the approved category base, rates them | approves the retained couples |
| **3 — Scénarios stratégiques** | By which route through the ecosystem would they get there? | strategic scenarios (source → stakeholders → essential asset) | writes one route per couple, then criticises its own list | rules on the **number** of scenarios (it sizes atelier 4) |
| **4 — Scénarios opérationnels** | How exactly would the attack unfold on the systems, and how likely is it to succeed? | *modes opératoires* in MITRE ATT&CK terms, a revised likelihood and risk level for each | lists every way in the dossier allows, then develops each one with an independent sub-agent | reviews all of them together, sends some back, picks which mode drives each risk |
| **5 — Traitement du risque** | What do we do about it, and what risk remains? | the risk map, the treatment plan, the residual risks, the monitoring framework | words each risk for a decision-maker, proposes measures, evaluates what remains, proposes indicators | decides the treatment option of each risk, reviews the plan, has the residual risks formally accepted |

### Rules the code enforces, whatever the model says

The model proposes through strict JSON schemas; code checks every answer before it
is kept. What the method fixes is computed or checked in code, never left to the model:

- **Nothing invented.** A justification must cite a real field of the Mission
  Context; a stakeholder, a control, an ATT&CK technique or mitigation id that does
  not exist in the dossier or the reference bases is refused.
- **Nothing silently dropped.** Every rejected proposal lands in *Éléments écartés*
  with its reason, and is shown to the auditor.
- **Levels are computed, not judged.** Pertinence, initial likelihood, risk level
  (gravité × vraisemblance), acceptability and measure priority come from fixed
  scales in code. Gravité is set once (atelier 1) and carried forward, never re-rated.
- **A security measure lowers the likelihood, never the gravité.** The residual
  likelihood can only go down, only where a measure is retained, and never further
  than the measures claim.
- **Reasons are mandatory.** Every skip, rejection, override, correction and
  decision needs a real justification; an empty or punctuation-only one is refused.
- **Quality checker.** Every atelier result is re-checked before approval; a result
  in *erreur* cannot be approved without typing `CONFIRMER`.

### What exists today

| Works | Not built yet |
|---|---|
| Intake + ateliers 1 to 5, each through its own CLI script | the mission report and the audit annex (`reporting/` is a placeholder) |
| Stop anywhere, resume with the same command | the web server (`main.py` is a placeholder; Docker starts nothing useful) |
| Versions, rollback cap, decision log, token accounting | an end-to-end run of ateliers 2 to 5 through the Orchestrator (it drives atelier 1 today) |
| `MANUAL_LLM=1` mode, without any API credit | |

---

## Setup

Python 3.13.

```bash
pip install -r requirements-dev.txt
```

Create a `.env` file at the root:

```
OPENROUTER_API_KEY=sk-or-...
# optional — the model used for every call (default: a free Gemma model for development)
MODEL_ID=anthropic/claude-sonnet-5
# optional — where things live (defaults shown)
MISSION_DB_PATH=data/mission/mission.db
ATTACK_DB_PATH=mitre_attack_complete.db
```

OpenRouter is the only model provider; `MODEL_ID` is the only thing to change
between a cheap test model and a production one.

- **The standards' controls** (ISO 27001, ANSSI hygiene, RGPD, NIST CSF) are read
  from the plugin folders at every run — no step needed.
- **The MITRE ATT&CK base** (`mitre_attack_complete.db`, shipped at the root) is
  needed from atelier 4 on: every technique and mitigation id is checked against it.
  It is opened read-only.

```bash
pytest
```

---

## Working with it — what is the same in every atelier

Everything runs in a terminal, in French. Run the scripts from a real terminal so the
prompts can read your answers.

### Answering the agent's questions

Each atelier opens with a short **session** of questions the dossier does not answer
yet (competitors for atelier 2, supplier access for atelier 4, acceptance threshold
and budget for atelier 5…). Answers are written back into the Mission Context, so
they are never asked twice. At any question you can:

- **answer** it;
- **ask** what it means (`c'est quoi un EDR ?`) — the agent explains and asks again;
- type **`skip`** — a reason is required, and the question is not put again;
- type **`!your text`** to force your answer verbatim when the agent keeps pushing back.

`--no-session` skips the session (ateliers 2 to 5).

### Questioning the agent

At the decision points the agent shows `Votre question :` — ask anything about the
result in front of you (*why is this mode the most likely?*). It answers **only from
the mission's own facts**, and says so when the dossier does not hold the answer.
Press Entrée to go on. In atelier 5's menus, type **`?`** to do the same before deciding.

### The approval gate

Every atelier ends with *« Approuvez-vous ce résultat ? »* — `oui` or `non` (a
refusal needs a reason). After a refusal:

- **`c` — correct it yourself.** Give the field path (`risques.0.vraisemblance_residuelle`),
  the new value, a justification. No model call. In ateliers 4 and 5, what follows
  from the value (a risk level, an acceptability, a priority) is recomputed.
- **`r` — let the agent redo it.** Where the atelier has several parts (1, 2, 4, 5),
  pick **which ones** to redo; the rest is kept verbatim. Your reasons are passed to
  the agent.
- **`q` — stop.** The last version is kept, marked *not approved*.

Every attempt is a new **version**; nothing is overwritten. After 3 versions of the
same atelier, going further requires typing `CONFIRMER`.

### Stopping and resuming

Stop whenever you like: `q` at a decision, or Ctrl+C. Every answer, every model
result and every decision is saved the moment it happens. **Run the same command
again** and the atelier resumes exactly where it stopped, without paying again for
a model call already made.

```bash
python scripts/run_workshop1_from_docs.py --list    # every mission and its status
```

The whole study lives in `data/mission/mission.db` — back it up by copying the file.

### Tokens and cost

```bash
python scripts/mission_tokens.py                 # all missions
python scripts/mission_tokens.py <mission_id>    # one mission, by model
```

Only tokens are counted; no price table is built in. Before any expensive step
(atelier 4's analyses, a second pass), the atelier shows the number of calls and an
estimate, and waits for your go.

### Without API credit

`MANUAL_LLM=1` writes each prompt to `data/manual/*.prompt.md` and waits for you to
drop the matching `.response.json` beside it. The schema travels with the prompt and
is enforced on what you write, so the result is checked exactly like a model answer.

---

## The five ateliers, step by step

### Intake and atelier 1 — cadrage et socle de sécurité

The client fills the Word questionnaire
([`docs/intake/Questionnaire_Contexte_EBIOS_RM.docx`](docs/intake/Questionnaire_Contexte_EBIOS_RM.docx)).
Any format is read (`.docx`, `.pdf`, `.txt`, `.md`; `.pdf` needs `pip install pdfplumber`).

```bash
python scripts/run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]
python scripts/run_workshop1_from_docs.py --resume <mission_id>
```

It prints the **`mission_id`** you will use for every later atelier. The agent reads
the documents, asks follow-ups for what is missing or thin, adds its own expert audit
questions, then proposes the assets, the feared events and the baseline assessment.

- **Same weakness, several standards.** ISO 27001, NIST and ANSSI often require the
  same fix. The agent proposes which gaps are one weakness; you confirm in one pass,
  and a confirmed group becomes one entry listing every control that requires it.
  Nothing is grouped without you.
- **Controls it could not conclude on** are listed as *unverified, with the reason*
  (information absent from the dossier, verdict without cited evidence, unknown
  control) — never counted as compliant. Type a control id only for those you want
  to document.
- **A declared standard with no controls loaded stops the run**: fill that
  plugin's `controls.json`, or withdraw the standard with a reason.
- **Redo** can target assets and feared events, baseline gaps, or legal impacts.

### Atelier 2 — sources de risque et objectifs visés

```bash
python scripts/run_workshop2.py <mission_id>
```

After an 8-question session, the agent proposes risk-source categories (only from
the approved base), the objectives they would pursue, and SR/OV couples rated on
three 1–4 scales. A proposal must describe an actor — not a technique or a system —
and justify itself from a named context field, or it is dropped with its reason.
Pertinence and initial likelihood are computed from the ratings. If atelier 1's
result has a broken reference, atelier 2 refuses to start: fix it in atelier 1.

### Atelier 3 — scénarios stratégiques

```bash
python scripts/run_workshop3.py <mission_id>
```

For each retained couple, the agent writes the route: which stakeholders of the
ecosystem the source goes through to reach which essential asset. It runs twice —
propose, then criticise and fold near-duplicates. A stakeholder the dossier never
mentions gets the scenario discarded.

Then the **count gate** — atelier 4 costs one call to list the modes opératoires per
scenario, plus one analysis per mode, so the number of scenarios decides its price:

- **up to 6** — validate or stop;
- **7 to 12** — validate anyway (with a reason), merge, choose a subset, or stop;
- **more than 12** — merge, choose a subset, or stop. *Run anyway* is not offered.

A merge or a subset needs a reason and comes back to the gate with the new count.

### Atelier 4 — scénarios opérationnels

```bash
python scripts/run_workshop4.py <mission_id>
```

The method's rule is followed as a real audit would: **develop every mode opératoire
the scenario allows, then keep the most likely** — not choose first, then develop.

1. **Listing the modes.** For each strategic scenario, the agent lists every way in
   the dossier supports — an exposed service, remote access, a supplier link, a
   person and their workstation, legitimate access misused, physical access — each
   tied to the context field that makes it real. The agent decides how many; a mode
   with no anchor, an unknown way in, or a twin of another is dropped with its
   reason. You see the list, the ways in the dossier names that no mode takes, and
   the price, then: `o` develop them all, `e` drop one (reason required), `a` add a
   way in the agent missed, `n` stop. Beyond 6 modes for one scenario, `CONFIRMER`
   is required.
2. **Developing them.** Each mode gets its own independent sub-agent (up to 4 in
   parallel): the attack path step by step in ATT&CK techniques
   (Connaître → Rentrer → Trouver → Exploiter), the baseline gaps it exploits, and a
   revised likelihood V1–V4. Every technique id is checked against the ATT&CK base,
   every gap must say what it changes. Each result is saved the moment it returns.
3. **Your review.** All results together, blocking anomalies first. `Entrée` confirms;
   type ids (`SO-02, SO-04`) to send them back — *revise* with your remarks, or
   *reject and redo*; `d SO-03` makes that mode the one that drives its scenario's
   risk (reason required). By default code picks the most likely mode. A mode can be
   analysed 3 times; beyond that, `CONFIRMER`.
4. **Coherence.** Once everything is stable, one call looks at the whole set
   (duplicates, likelihoods that contradict each other). Accept its findings, reopen
   the modes concerned, or dismiss them with a reason.

The gate's redo can target individual modes.

### Atelier 5 — traitement du risque

```bash
python scripts/run_workshop5.py <mission_id>
```

A 4-question session first: the acceptance threshold and who pronounces it, the
means available this year, who carries measures by kind, how often an instance can
follow the plan. Then the method's five activities, in order:

1. **The risk map (5-1).** One risk per strategic scenario: its gravité from atelier
   1, its likelihood from the mode atelier 4 kept. The agent words each risk in one
   sentence a director can read. The map is printed (gravité × vraisemblance), and
   every **serious feared event of atelier 1 that no risk carries** is flagged — the
   method then asks to iterate ateliers 2 to 4; continuing needs a reason.
2. **The treatment strategy (5-2) — your decision.** For each risk the scale says
   *acceptable*, *tolérable sous contrôle* or *inacceptable*, and proposes an option;
   you choose: `r` réduire, `m` maintenir, `p` partager, `e` éviter, with a reason.
   Keeping an unacceptable risk as it is requires `CONFIRMER`.
3. **The treatment plan (5-3).** One call builds the whole plan, so a measure can
   serve several risks. Measures are filed in the method's four axes (gouvernance,
   protection, défense, résilience) and must break a step of a mode, close a baseline
   gap, or treat a risk; ATT&CK mitigation ids are kept only if the base returned them
   for the techniques the modes cite. Each carries owner, obstacles, cost (+/++/+++),
   workload, deadline, and a priority computed from the risk level first, then the
   cost. You review it: `v` validate, `r` set owner/workload/deadline, `e` drop
   measures (reason required), `c` ask the agent to complete it.
4. **The residual risks (5-4).** The agent evaluates each treated risk once the plan
   is in place — mode by mode; the risk keeps the likelihood of its most likely
   remaining mode. Code refuses any rise, any drop without a measure, and any drop
   larger than the measures claim. Then the residual risks are **formally accepted**,
   by name and function — or `p` sends you back to strengthen the plan (the earlier
   acceptance is then void).
5. **The monitoring framework (5-5).** You give the follow-up instance and its
   cadence; the agent proposes 3 to 8 measurable indicators (a cost, a duration, a
   count or a rate, each with a target).

The gate's redo can target the wording, the options (the plan follows), the plan and
residual risks, or the monitoring framework.

---

## Where things live

```
scripts/                 one command per atelier, plus tokens and questionnaire tools
src/ebios_rm/
  mission_context/       intake: questionnaire reading, facts, validation, follow-ups, clarification
  workshops/             one package per atelier: models, prompts, checks (assessment.py), agent
  orchestrator/          the interactive flows, approval gate, mission state (save/load/resume)
  domain/                shared models: facts, assets, feared events, scenarios, measures
  repositories/          SQLite access: missions, reference controls, ATT&CK (read-only)
  services/              cost estimation (the rest is placeholder)
  db/                    schemas and the reference-base loader
  plugins/frameworks/    one folder per standard or law
  reporting/, toolkits/  placeholders
data/mission/            the missions (mission.db)
docs/intake/             the questionnaire and a filled example
tests/                   no test calls a real model
```

In each atelier package, `assessment.py` holds the method's rules as pure functions,
`prompts.py` everything the model reads, `workshop.py` the steps, and the matching
`orchestrator/workshopN_flow.py` (or `scripts/run_workshopN.py`) the conversation
with the auditor.

## Adding a standard or a law

Each framework lives in `src/ebios_rm/plugins/frameworks/<framework_id>/`:

- `manifest.yaml` — id, display name, version, legal nature, whether it carries
  purely legal provisions (fines, mandatory notification);
- `controls.json` — its controls.

The folder is discovered at load time; adding a standard never touches atelier or
agent code. Start from `plugins/frameworks/_template/`.
