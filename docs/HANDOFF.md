# Handoff — EBIOS RM agent, state at end of Workshop 1

Read this before touching anything. It is written so a new session can continue
without re-deriving decisions: what exists, why it is the way it is, what was
deliberately *not* built, and what to do next.

Repo: `https://github.com/mynameisalae/EBIOS-RM` (branch `main`)
Reference document: [`docs/conception/CONCEPTION.md`](conception/CONCEPTION.md) —
every `§n` in the code points at one of its sections. It is authoritative; when
this handoff and the conception disagree, the conception wins unless the
deviation is listed below.

---

## 1. What the product is

An AI agent assisting a human auditor through an EBIOS Risk Manager mission
(ANSSI method, 5 ateliers). The founding rule (§2): the system is **AI-assisted,
never AI-driven**. The AI extracts, analyses, proposes, cites, flags gaps and
contradictions, and generates questions. It never invents information, never
assumes a missing value, never resolves a contradiction alone, never approves an
atelier. The auditor always has the last word.

That rule is not decoration — most of the code exists to enforce it mechanically
rather than trusting the model to behave.

## 2. Stack, and one deviation that matters

| Piece | Choice |
|---|---|
| Language | Python 3.13 |
| Agent framework | Agno 2.6.12 |
| Model provider | OpenRouter, **sole provider**, test and prod |
| Dev model | `google/gemma-4-26b-a4b-it:free` |
| Prod model | swap `MODEL_ID` (e.g. `anthropic/claude-sonnet-5`) |
| Storage | SQLite ×2 — reference (read-only) + mission (read-write) |
| Docs | pandoc (.docx), pdfplumber (.pdf) |

**Deviation from §15, deliberate:** the conception specifies an Agno *Toolkit*
(`get_baseline_controls`, `assess_control`…) and Agno's native HITL. Neither is
used. Free models do not reliably support tool calling — §3.2 predicted exactly
this. Instead the agent is driven purely by **structured output** (`output_schema`)
and the referential queries run in code, their results injected into the prompt.
Human decisions go through our own `HumanInterface`, which is testable without a
terminal. Both were verified against the real model; do not "fix" them back.

`get_gap_consequences` from the §15 toolkit list was never built — the conception
never says what it does.

## 3. Where things are

```
src/ebios_rm/
  agent_runtime.py            run_structured(): the retry/backoff/type-check loop
                              EVERY LLM call goes through. Token capture hooks here.
  config.py                   get_model() — the only place a model name exists (§3.2)
  domain/                     Fact (provenance enforced in the model), enums, assets,
                              feared events
  mission_context/
    questionnaire.py          65-question catalog — single source for the client Word
                              doc AND for ingestion
    document_reader.py        .docx/.pdf/.md/.txt -> text
    ingestion.py + _agent     read a filled questionnaire -> cited Facts + plausibility
                              flags
    validation.py             the three cases (identical / doc-only / contradiction)
    priority_matrix.py        Critical vs Important, what still needs asking
    conversation.py           one LLM turn: is this an answer, a question, or too vague?
    clarification*.py         auditor asks, agent answers strictly from context
    mission_context.py        the consolidated validated-Fact object
  workshops/workshop1_cadrage/
    intake_ingestion.py       the intake orchestration + checkpointing + resume
    human_interface.py        every human decision point (follow-ups, flags,
                              contradictions, approval)
    auditor_review.py         agent generates its OWN expert follow-up questions
    workshop.py               run_workshop1(): cadrage / baseline / legal, block-selectable
    assessment.py             pure rules: evidence discipline, unverified reasons,
                              scope decisions
    gap_dedup.py              one gap per weakness across referentials
    human_edit.py             auditor corrects a value, with provenance
    prompts.py                the workshop agent's prompts
  plugins/frameworks/         one folder per referential (manifest + controls.json)
  repositories/               reference (controls) + mission (persistence)
  orchestrator/mission_state.py  typed save/load, rollback cap

scripts/run_workshop1_from_docs.py   THE runner. Also the de-facto orchestrator (see §7).
scripts/mission_tokens.py            token usage per mission
scripts/generate_intake_questionnaire.py
```

## 4. The Workshop 1 pipeline, end to end

```
filled questionnaire (.docx/.pdf) [+ optional supporting docs]
  -> extraction: each answer becomes a Fact with its source quote
  -> plausibility check: the agent flags nonsense answers; the auditor rules
  -> validation: identical / document-only / contradiction (never auto-resolved)
  -> catalog follow-ups for what is still missing (Critical blocks, Important
     skippable with a reason)
  -> expert review: the agent writes its OWN questions from the context,
     in rounds, until it has nothing left to ask
  -> Mission Context (validated Facts only)
  -> workshop: assets, feared events (gravité ×4, impact ×5), baseline gaps,
     legal impacts
  -> gap consolidation: one entry per weakness, listing every referential
  -> unverified controls shown with WHY
  -> clarification: the auditor questions the agent
  -> approval gate: approve / edit / redo
```

## 5. Design decisions you must not silently undo

Each of these was argued and chosen; reverting one reintroduces a real failure.

1. **Evidence discipline.** A `gap` or `compliant` verdict without a cited quote
   is refused in code and becomes `unverified`. The model cannot talk past it.
2. **`unverified` is never reclassified.** Four distinct reasons are recorded
   (`no_information`, `no_evidence_cited`, `unknown_control`, `invalid_verdict`).
   They are not interchangeable: `no_evidence_cited` is a *prompt* problem, not a
   question for the auditor. **No per-control interrogation** — with 248 controls
   that guarantees the auditor abandons and the trail fills with empty
   justifications. They read the list and document only what they choose.
3. **Contradictions and merges are never automatic.** The agent proposes, the
   auditor confirms.
4. **`intent` is stated by the model** (`answer` / `question` / `insufficient`),
   never inferred from reply text. An earlier "does the reply contain '?'"
   heuristic both missed imperative requests and blocked valid answers.
5. **`!` escape hatch.** The auditor can force-record a raw answer. Without it a
   model that keeps demanding detail traps a blocking question forever — the AI
   would outrank the human, inverting §2.
6. **Skip must be typed.** A blank Enter never starts a skip.
7. **Missing controls stop the run.** A declared framework with zero controls
   cannot be assessed; the AI must not invent referential text. Load the controls
   or withdraw the framework with a logged reason.
8. **A failed LLM call is never a methodology outcome.** It retries, then raises
   or degrades to "nothing proposed" — never an empty gap list read as "clean".
9. **Partial redo.** Rejecting a wrong gravité must not reshuffle assets the
   auditor liked, nor pay for calls nobody asked for.
10. **Checkpoint after every answer.** The interview is the expensive part; a
    crash must not cost it.

## 6. Licensed content — do not commit

`src/ebios_rm/plugins/frameworks/iso27001/controls.json` is **gitignored**.
ISO/IEC 27001 Annex A is AFNOR-licensed, internal use only (§12.2) — it must not
be redistributed, including in git. The manifest is committed (declares the
framework, no licensed text); see that folder's README.

ANSSI (42), NIST CSF 2.0 (101), RGPD (12) are freely reusable and committed.
ISO (93) exists locally only. Total when all present: 248.

Note for honesty: the ISO text *was* pushed in commit `b464783` before this was
caught. The user decided against rewriting history. Do not re-add it.

## 7. Known weaknesses (real, not nitpicks)

- **`scripts/run_workshop1_from_docs.py` is ~590 lines and is now the
  orchestrator**, not a "dev runner": it holds the controls gate, redo loop,
  edit, consolidation, approval, token sink. `src/ebios_rm/orchestrator/` is still
  an empty placeholder. Tests reach this flow by monkeypatching module globals —
  a smell. **Move the flow into `orchestrator/` when Workshop 2 starts**, because
  Workshop 2 needs the §10.2 handoff (`Atelier N -> Mission State -> Orchestrateur
  -> N+1`) anyway. Doing it earlier would design that contract blind.
- 27 placeholder modules (toolkits, services, reporting, workshops 2-5) hold 0-5
  lines each. They mirror the conception's structure; kept deliberately.
- `mission.status` currently carries workshop status (`w1_approved`). When
  Workshop 2 exists, split: mission-level status vs per-workshop status (the
  latter already lives in `workshop_versions`).
- Consolidation recall depends on model judgement; a missed pair leaves two rows.
- Cost: 248 controls means one large call per framework. Token totals per mission
  are recorded (`scripts/mission_tokens.py`); **money is deliberately 0** — no
  price table baked in.

## 8. What is NOT built

Workshops 2-5, the orchestrator, the reporting agent (§20), ATT&CK loading,
mid-ingestion resume (rejected: it re-runs 6 automated calls, not worth the
complexity).

## 9. Test posture — read this before trusting "109 tests pass"

All 109 tests use **fakes**: scripted auditor, canned agent responses, **no LLM**.
They prove the machinery (bounds, guards, provenance, resume, consolidation
arithmetic). They prove **nothing** about output quality.

```bash
pytest                                    # 109 pass, 6 skipped (workshops 2-5)
```

Fixtures build the reference DB with `include_plugins=False` so tests stay
deterministic as referential text changes.

## 10. Where the work stands, and the next step

Workshop 1 is **feature-complete against §15** (with the §2 deviations above) and
has been exercised live end to end: ingestion of a real 20K-char PDF, expert
questions generated from context, gaps, legal impacts, persistence and resume.

What has *not* been validated is **output quality with the real 248 controls**:
consolidation groups, expert-question relevance, gravité justification, and the
`unverified` reason breakdown. A run dominated by `no_evidence_cited` means the
prompt is at fault, not the client — that breakdown is the diagnostic.

The five prompts to tune are listed in
`C:\Users\user\Desktop\EBIOS_RM_prompt_tuning_handoff.txt`, which has a slot for
pasting a real interaction.

**Suggested next step:** either (a) tune prompts from a real run, or (b) start
Workshop 2 (`Sources de risque`, §16) — which is the moment to extract the
orchestrator and split mission/workshop status. Ask the user which; do not assume.

## 11. How to run

```bash
python scripts/run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]
python scripts/run_workshop1_from_docs.py --list
python scripts/run_workshop1_from_docs.py --resume <mission_id>
python scripts/mission_tokens.py [<mission_id>|--prune]
PYTHONPATH=src python -m ebios_rm.db.loader     # rebuild reference DB after editing a plugin
```

Needs `OPENROUTER_API_KEY` in `.env`. Run from a real terminal (interactive
prompts). Ctrl+C pauses cleanly and prints the resume command.

## 12. Working agreement with this user

- Commits: **never add Claude as co-author.**
- They run `/ponytail` (laziest solution that works) and `/caveman` (terse prose)
  permanently. Match it: no filler, no over-building, question whether a thing
  needs to exist before building it.
- They push back on weak reasoning and are usually right — the weakness-centric
  gap model and the "explain why it's unverified" design were both their calls,
  and both beat what was proposed. Argue honestly, then defer.
- Do not code when they say "don't code yet" — they want the plan first.
