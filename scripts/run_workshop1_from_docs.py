"""Dev runner for Workshop 1 via DOCUMENT INGESTION (conception §11, §15).

    python scripts/run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]

Example:
    python scripts/run_workshop1_from_docs.py data/dev_seed/example_filled_questionnaire.md

What it does:
1. Reads the filled intake questionnaire (.md/.txt/.docx; .pdf if pdfplumber installed).
2. The agent extracts each answer into a cited Fact and FLAGS any answer that does
   not make sense — you rule on each flag.
3. Reads any supporting documents you pass, extracting cited Facts from them;
   contradictions with the questionnaire are sent to you to resolve.
4. Asks follow-up questions for anything still missing (over the full catalog).
5. Runs Workshop 1 and prints w1_output.

Requires OPENROUTER_API_KEY (.env) and `pip install -r requirements.txt`. Run from
a real terminal so the interactive prompts work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.db.loader import build_reference_db  # noqa: E402
from ebios_rm.repositories.reference_repository import ReferenceRepository  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_documents  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1  # noqa: E402

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]")
        return 2

    settings = load_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set — put it in .env before running.")
        return 2
    print(f"Model: {settings.model_id}  (OpenRouter)")

    intake_doc = argv[1]
    supporting = argv[2:]

    reference_repo = ReferenceRepository(
        build_reference_db(":memory:", extra_controls=json.loads(DEV_SEED.read_text(encoding="utf-8")))
    )
    from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
    human = ConversationalHumanInterface(AgnoConversationRunner())

    from ebios_rm.mission_context.ingestion_agent import AgnoIngestionRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.auditor_review import AgnoAuditorReviewRunner  # noqa: PLC0415

    print("\n=== Phase 1 : ingestion des documents (l'agent lit, vous décidez) ===")
    mission_context = complete_intake_from_documents(
        intake_doc, supporting, AgnoIngestionRunner(), human, AgnoAuditorReviewRunner()
    )
    print(f"\nMission Context : {len(mission_context.facts)} faits validés.")

    print("\n=== Phase 2 : atelier 1 ===")
    output = run_workshop1(mission_context, AgnoWorkshop1Runner(), reference_repo)

    print("\n=== w1_output ===")
    print(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2))

    # Two-way clarification: you can now ask the agent about the mission / the result.
    from ebios_rm.mission_context.clarification import clarification_repl  # noqa: PLC0415
    from ebios_rm.mission_context.clarification_agent import AgnoClarificationRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop  # noqa: PLC0415

    clarification_repl(AgnoClarificationRunner(), mission_context, output)

    approved, reason = approve_workshop("l'atelier 1")
    if not approved:
        print(f"Atelier 1 non approuvé : {reason}")
        return 1
    print("Atelier 1 approuvé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
