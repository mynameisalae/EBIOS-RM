"""Dev runner for Workshop 5 — traitement du risque (conception §19; méthode atelier 5).

    # run atelier 5 on a mission whose atelier 4 is approved
    python scripts/run_workshop5.py <mission_id>

    # skip the client session (use the context as-is)
    python scripts/run_workshop5.py <mission_id> --no-session

Reads the Mission Context and the approved outputs of ateliers 1 to 4 from the mission
DB, holds the séance, then runs the five activities of the method in order: the risk map
and its completeness check against atelier 1's feared events (5-1), the treatment option
the auditor decides for each risk (5-2), the treatment plan in its four axes with the
ATT&CK mitigations of the techniques the modes cite (5-3), the residual risks and their
formal acceptance (5-4), and the monitoring framework (5-5) — then asks for approval.

Stop at any time — Ctrl+C, or 'q' at a decision. Every answer and every decision is
saved as it happens, and the same command resumes where it stopped, without paying
again for a call already made.

Requires OPENROUTER_API_KEY (.env) and `pip install -r requirements.txt` (or
MANUAL_LLM=1). Run from a real terminal so the interactive prompts work.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.agent_runtime import StructuredCallFailed, set_token_sink  # noqa: E402
from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.orchestrator.approval_cli import interrupted  # noqa: E402
from ebios_rm.orchestrator.workshop5_flow import Workshop5NotReady, run_workshop5  # noqa: E402
from ebios_rm.repositories.attack_repository import (  # noqa: E402
    AttackRepository,
    AttackRepositoryError,
    connect_readonly,
)
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.workshops.common import AtelierDataError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run atelier 5 on a saved mission.")
    parser.add_argument("mission_id")
    parser.add_argument("--no-session", action="store_true", help="skip the atelier 5 session questions")
    args = parser.parse_args()

    settings = load_settings()
    print(f"Model: {settings.model_id}  (OpenRouter)")
    repo = MissionRepository(connect(settings.mission_db_path))

    try:
        # The plan may only cite ATT&CK mitigation ids the base returned for the techniques
        # the modes opératoires actually cite (§19) — without the base, nothing runs.
        attack = AttackRepository(connect_readonly(settings.attack_db_path))
        attack.version()
    except AttackRepositoryError as exc:
        print(f"{exc}\nL'atelier 5 ne peut rattacher aucune mesure ATT&CK : renseignez ATTACK_DB_PATH.")
        return 1

    mission = repo.get_mission(args.mission_id)
    if mission is not None:
        print(f"Mission {mission.mission_id} — {mission.name}")
    set_token_sink(lambda inp, out, model: repo.log_tokens(
        args.mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    # Imported here: they resolve the model, which MANUAL_LLM and a missing key handle differently.
    from ebios_rm.mission_context.clarification_agent import AgnoClarificationRunner  # noqa: PLC0415
    from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import (  # noqa: PLC0415
        ConversationalHumanInterface,
    )
    from ebios_rm.workshops.workshop5_traitement_risque.agent import AgnoWorkshop5Runner  # noqa: PLC0415

    human = None
    if not args.no_session:
        # As in atelier 1's intake: the auditor can answer, ask what a question means,
        # type 'skip' with a reason, or force an answer with '!'.
        human = ConversationalHumanInterface(AgnoConversationRunner())
    try:
        return run_workshop5(repo, args.mission_id, attack, AgnoWorkshop5Runner(),
                             human=human, clarifier=AgnoClarificationRunner())
    except Workshop5NotReady as exc:
        print(exc)
        return 1
    except AtelierDataError as exc:
        print(f"\n{exc}")
        print("Corrigez l'atelier 4 avant de relancer — l'atelier 5 ne répare rien de lui-même.")
        return 1


if __name__ == "__main__":
    _resume = f"python scripts/run_workshop5.py {sys.argv[1] if len(sys.argv) > 1 else '<mission_id>'}"
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(interrupted("l'atelier 5", _resume)) from None
    except StructuredCallFailed as exc:
        # A failed call is never a plan; every decision already taken is saved.
        print(f"\nAppel au modèle en échec : {exc}")
        raise SystemExit(interrupted("l'atelier 5", _resume)) from None
