"""Dev runner for Workshop 1 — end-to-end, interactive, against OpenRouter.

    PYTHONPATH=src python scripts/run_workshop1_dev.py data/dev_seed/example_intake.json

What it does (conception §11, §15):
1. Loads a filled intake form (JSON matching org_context_form).
2. Builds an in-memory reference DB from the framework plugins + the clearly
   labelled dev sample controls (data/dev_seed/), so the baseline + legal-impact
   paths are exercisable without a licensed control set.
3. Completes the intake interactively on the terminal — follow-up questions for
   missing fields, confirmation of document-only values, contradiction
   resolution (all decided by you, the auditor).
4. Runs the Workshop 1 agent (nvidia/nemotron-3-ultra-550b-a55b:free by default)
   and prints the validated w1_output as JSON.

Requirements: set OPENROUTER_API_KEY in your environment (or .env), install
`agno` (pip install -r requirements.txt), and run from a real terminal so stdin
prompts work. Optional document extraction is not wired in this dev runner yet —
pass an empty document set; the intake + follow-up + baseline flow runs fully.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows consoles default to cp1252 when stdout is redirected/piped, which crashes
# on non-latin1 characters (e.g. the "↳" hint marker) and mangles accents. Force UTF-8.
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.db.loader import build_reference_db  # noqa: E402
from ebios_rm.mission_context.intake_form import OrgContextForm  # noqa: E402
from ebios_rm.repositories.reference_repository import ReferenceRepository  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.human_interface import CLIHumanInterface  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.workshop import complete_intake, run_workshop1  # noqa: E402

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run_workshop1_dev.py <filled_intake.json>")
        return 2

    settings = load_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set — export it (or put it in .env) before running.")
        return 2
    print(f"Model: {settings.model_id}  (OpenRouter)")

    form = OrgContextForm.model_validate_json(Path(argv[1]).read_text(encoding="utf-8"))

    extra_controls = json.loads(DEV_SEED.read_text(encoding="utf-8"))
    conn = build_reference_db(":memory:", extra_controls=extra_controls)
    reference_repo = ReferenceRepository(conn)

    human = CLIHumanInterface()

    print("\n=== Phase 1 : complétion du contexte (vous êtes l'auditeur) ===")
    mission_context = complete_intake(form, extraction_facts=[], human=human)
    print(f"\nMission Context construit : {len(mission_context.facts)} faits validés.")

    print("\n=== Phase 2 : atelier 1 (l'agent propose, le code valide) ===")
    # Imported here so Phase 1 (no LLM) can run even if agno is missing.
    from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner  # noqa: PLC0415

    output = run_workshop1(mission_context, AgnoWorkshop1Runner(), reference_repo)

    print("\n=== w1_output ===")
    print(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print("\nbaseline_gaps_for_w4 (stripé pour l'atelier 4) :")
    print(json.dumps([g.model_dump(mode="json") for g in output.baseline_gaps_for_w4()], ensure_ascii=False, indent=2))

    from ebios_rm.mission_context.clarification import clarification_repl  # noqa: PLC0415
    from ebios_rm.mission_context.clarification_agent import AgnoClarificationRunner  # noqa: PLC0415

    clarification_repl(AgnoClarificationRunner(), mission_context, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
