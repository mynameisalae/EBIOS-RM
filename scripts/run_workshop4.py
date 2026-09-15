"""Dev runner for Workshop 4 — scénarios opérationnels (conception §18).

    # run atelier 4 on a mission whose atelier 3 is approved
    python scripts/run_workshop4.py <mission_id>

    # skip the client session (use the context as-is)
    python scripts/run_workshop4.py <mission_id> --no-session

Reads the Mission Context and the approved outputs of ateliers 1 to 3 from the
mission DB, holds the session, analyses every strategic scenario with its own
sub-agent against the ATT&CK base (ATTACK_DB_PATH, default mitre_attack_complete.db),
puts all the analyses to the auditor together, runs the coherence check once the set
is stable, and asks for approval.

Stop at any time — Ctrl+C, or 'q' at a decision. Every analysis and every decision is
saved as it happens, and the same command resumes where it stopped, without paying
again for an analysis already made.

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
from ebios_rm.orchestrator.workshop4_flow import Workshop4NotReady, run_workshop4  # noqa: E402
from ebios_rm.repositories.attack_repository import (  # noqa: E402
    AttackRepository,
    AttackRepositoryError,
    connect_readonly,
)
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.workshops.workshop4_scenarios_operationnels import Atelier3DataError  # noqa: E402
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent import Workshop4AgentError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run atelier 4 on a saved mission.")
    parser.add_argument("mission_id")
    parser.add_argument("--no-session", action="store_true", help="skip the atelier 4 session questions")
    args = parser.parse_args()

    settings = load_settings()
    print(f"Model: {settings.model_id}  (OpenRouter)")
    repo = MissionRepository(connect(settings.mission_db_path))

    try:
        # The catalogue is what every cited technique id is checked against (§18 step 23):
        # without it the sub-agents could only be trusted, so nothing runs.
        catalogue = AttackRepository(connect_readonly(settings.attack_db_path)).catalogue()
    except AttackRepositoryError as exc:
        print(f"{exc}\nL'atelier 4 ne peut vérifier aucune technique : renseignez ATTACK_DB_PATH.")
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
    from ebios_rm.workshops.workshop4_scenarios_operationnels.agent import AgnoWorkshop4Runner  # noqa: PLC0415

    human = None
    if not args.no_session:
        # As in atelier 1's intake: the auditor can answer, ask what a question means,
        # type 'skip' with a reason, or force an answer with '!'.
        human = ConversationalHumanInterface(AgnoConversationRunner())
    try:
        return run_workshop4(repo, args.mission_id, catalogue, AgnoWorkshop4Runner(),
                             human=human, clarifier=AgnoClarificationRunner())
    except Workshop4NotReady as exc:
        print(exc)
        return 1
    except Atelier3DataError as exc:
        print(f"\n{exc}")
        print("Corrigez l'atelier 3 avant de relancer — l'atelier 4 ne répare rien de lui-même.")
        return 1


if __name__ == "__main__":
    _resume = f"python scripts/run_workshop4.py {sys.argv[1] if len(sys.argv) > 1 else '<mission_id>'}"
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(interrupted("l'atelier 4", _resume)) from None
    except (Workshop4AgentError, StructuredCallFailed) as exc:
        # A failed call is never an analysis; the scenarios that succeeded are saved.
        print(f"\nAppel au modèle en échec : {exc}")
        raise SystemExit(interrupted("l'atelier 4", _resume)) from None
