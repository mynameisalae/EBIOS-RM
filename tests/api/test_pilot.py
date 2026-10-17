"""Piloter une mission depuis le web : le terminal prêté à une page.

Fake ateliers stand in for the models; the Orchestrator, the approval gates and the channel are real.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from ebios_rm.api.app import create_app
from ebios_rm.api.pilot import Channel, Interrupted
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state, state_machine
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output


class FakeOutput(BaseModel):
    note: str = "ok"


class FakeWorkshop:
    def __init__(self, n: int, output: BaseModel | None = None) -> None:
        self.workshop_number = n
        self._output = output or FakeOutput(note=f"atelier {n}")
        self.runs = 0

    async def run(self, input, mission_id):
        self.runs += 1
        return self._output

    def stop(self) -> None:
        pass

    async def resume(self, mission_id):
        return self._output

    def summarize_output(self, output) -> str:
        return f"Résumé de l'atelier {self.workshop_number}"


def fake_workshops(repo, channel):
    return {1: FakeWorkshop(1, Workshop1Output()), 2: FakeWorkshop(2)}


def fake_intake(repo, mission_id, channel, files):
    channel.say("=== Collecte du contexte ===")
    assert channel.ask("Votre secteur ? ") == "Santé"
    mission_state.save_mission_context(repo, mission_id, MissionContext(
        organisation_nom="Org Test", secteur_activite="Santé", applicable_frameworks=["RGPD"],
        facts=[Fact.declaration("hebergement", "hybride")]))
    repo.set_status(mission_id, state_machine.MissionStatus.CONTEXT_READY)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "mission.db")
    repo = MissionRepository(connect(path))
    mission_id = repo.create_mission("Mission Test", ["RGPD"])
    mission_state.save_mission_context(repo, mission_id, MissionContext(
        organisation_nom="Org Test", secteur_activite="Santé", applicable_frameworks=["RGPD"],
        facts=[Fact.declaration("hebergement", "hybride")]))
    repo.set_status(mission_id, state_machine.MissionStatus.CONTEXT_READY)
    return path, mission_id


@pytest.fixture
def client(db, tmp_path):
    path, _ = db
    return TestClient(create_app(path, uploads_dir=tmp_path / "uploads", workshops=fake_workshops, intake=fake_intake))


def wait_for(client, session_id, condition, seconds: float = 5.0) -> dict:
    deadline = time.time() + seconds
    state: dict = {}
    while time.time() < deadline:
        state = client.get(f"/api/pilote/{session_id}").json()
        if condition(state):
            return state
        time.sleep(0.02)
    raise AssertionError(f"condition jamais remplie : {state}")


def asks(text_part: str):
    return lambda s: s["prompt"] is not None and text_part in s["prompt"]["text"]


def answer(client, session_id, state, text: str) -> None:
    response = client.post(f"/api/pilote/{session_id}/reponse", json={"prompt_id": state["prompt"]["id"], "text": text})
    assert response.status_code == 200


# --- the channel: what a person sees of a terminal question ---


def test_a_yes_no_question_becomes_two_buttons():
    channel = Channel()
    threading.Thread(target=channel.ask, args=("Approuvez-vous ce résultat ? [oui / non] : ",), daemon=True).start()
    time.sleep(0.1)
    prompt = channel.snapshot()["prompt"]
    assert prompt["kind"] == "yesno"
    assert [o["key"] for o in prompt["options"]] == ["oui", "non"]


def test_a_menu_printed_before_the_prompt_becomes_choices():
    channel = Channel()
    channel.say("")
    channel.say("Que faire de cette liste ?")
    channel.say("   [1] valider cette liste")
    channel.say("   [2] en rester là")
    threading.Thread(target=channel.ask, args=("> ",), daemon=True).start()
    time.sleep(0.1)
    prompt = channel.snapshot()["prompt"]
    assert prompt["kind"] == "choice"
    assert prompt["options"] == [{"key": "1", "label": "valider cette liste"}, {"key": "2", "label": "en rester là"}]


def test_free_text_stays_free_text_and_the_confirmation_word_is_flagged():
    channel = Channel()
    channel.say("Tapez CONFIRMER pour approuver malgré tout")
    threading.Thread(target=channel.ask, args=("> ",), daemon=True).start()
    time.sleep(0.1)
    prompt = channel.snapshot()["prompt"]
    assert prompt["kind"] == "text" and prompt["confirm"] is True


def test_an_answer_reaches_the_flow_once_and_only_for_the_pending_question():
    channel = Channel()
    got: list[str] = []
    threading.Thread(target=lambda: got.append(channel.ask("Nom ? ")), daemon=True).start()
    time.sleep(0.1)
    prompt_id = channel.snapshot()["prompt"]["id"]
    assert channel.answer(prompt_id + 5, "x") is False          # not the pending question
    assert channel.answer(prompt_id, "Alice") is True
    time.sleep(0.1)
    assert got == ["Alice"]
    assert channel.answer(prompt_id, "Bob") is False            # already answered
    assert "> Alice" in channel.snapshot()["lines"]             # the exchange stays in the journal


def test_interrupting_frees_a_waiting_flow():
    channel = Channel()
    raised: list[bool] = []

    def flow():
        try:
            channel.ask("Nom ? ")
        except Interrupted:
            raised.append(True)

    thread = threading.Thread(target=flow, daemon=True)
    thread.start()
    time.sleep(0.1)
    channel.interrupt()
    thread.join(2)
    assert raised == [True]


# --- the whole thing through the API ---


def test_a_mission_ready_to_run_offers_to_be_launched(client, db):
    _, mission_id = db
    step = client.get(f"/api/missions/{mission_id}").json()["next_step"]
    assert step["can_pilot"] is True and "atelier 1" in step["label"]


def test_running_a_mission_stops_at_each_gate_until_the_auditor_decides(client, db):
    path, mission_id = db
    session = client.post(f"/api/missions/{mission_id}/pilote").json()["session_id"]

    gate1 = wait_for(client, session, asks("Approuvez-vous"))
    assert any("Validation de Atelier 1" in line for line in gate1["lines"])
    assert gate1["status"] == "running"
    answer(client, session, gate1, "oui")

    gate2 = wait_for(client, session, lambda s: asks("Approuvez-vous")(s) and s["prompt"]["id"] != gate1["prompt"]["id"])
    assert any("Validation de Atelier 2" in line for line in "\n".join(gate2["lines"]).split("\n"))
    answer(client, session, gate2, "oui")

    done = wait_for(client, session, lambda s: s["status"] == "done")
    assert done["final_status"] == state_machine.approved(2)
    assert MissionRepository(connect(path)).get_mission(mission_id).status == state_machine.approved(2)


def test_a_refusal_asks_for_a_reason_then_redoes_the_atelier(client, db):
    path, mission_id = db
    session = client.post(f"/api/missions/{mission_id}/pilote").json()["session_id"]

    gate = wait_for(client, session, asks("Approuvez-vous"))
    answer(client, session, gate, "non")
    reason = wait_for(client, session, asks("Motif du refus"))
    assert reason["prompt"]["kind"] == "text"
    answer(client, session, reason, "Les événements redoutés sont trop vagues")

    again = wait_for(client, session, lambda s: asks("Approuvez-vous")(s) and s["prompt"]["id"] > reason["prompt"]["id"])
    answer(client, session, again, "oui")
    log = MissionRepository(connect(path)).decisions(mission_id)
    assert [d.action_taken for d in log if d.stage == "w1"][:2] == ["rejected", "approved"]


def test_interrupting_a_session_keeps_the_mission_where_it_was(client, db):
    path, mission_id = db
    session = client.post(f"/api/missions/{mission_id}/pilote").json()["session_id"]
    wait_for(client, session, asks("Approuvez-vous"))
    assert client.post(f"/api/pilote/{session}/arret").status_code == 200
    stopped = wait_for(client, session, lambda s: s["status"] == "stopped")
    assert stopped["prompt"] is None
    assert client.post(f"/api/pilote/{session}/arret").status_code == 409   # nothing left to stop
    # The mission has not been approved behind the auditor's back.
    assert MissionRepository(connect(path)).get_mission(mission_id).status == state_machine.awaiting_approval(1)


def test_one_mission_is_driven_at_a_time(client, db, tmp_path):
    path, mission_id = db
    other = MissionRepository(connect(path)).create_mission("Autre", [])
    session = client.post(f"/api/missions/{mission_id}/pilote").json()["session_id"]
    wait_for(client, session, asks("Approuvez-vous"))
    busy = client.post("/api/missions", files={"questionnaire": ("q.md", b"x")})
    assert busy.status_code == 409
    assert "déjà en cours" in busy.json()["detail"]
    assert len(MissionRepository(connect(path)).list_missions()) == 2     # no mission left behind
    # Asking again for the mission being driven gives back its session instead of starting another.
    assert client.post(f"/api/missions/{mission_id}/pilote").json()["session_id"] == session
    assert other != mission_id


def test_a_new_mission_starts_from_its_questionnaire(client, db):
    path, _ = db
    started = client.post("/api/missions", files={
        "questionnaire": ("mondial_rempli.md", b"# Questionnaire"),
        "supporting": ("politique.pdf", b"%PDF"),
    }).json()
    session, mission_id = started["session_id"], started["mission_id"]

    question = wait_for(client, session, asks("Votre secteur"))
    answer(client, session, question, "Santé")
    wait_for(client, session, asks("Approuvez-vous"))                  # intake done, atelier 1 ran

    repo = MissionRepository(connect(path))
    assert repo.get_mission(mission_id).name == "mondial_rempli"
    assert repo.get_mission(mission_id).status == state_machine.awaiting_approval(1)
    client.post(f"/api/pilote/{session}/arret")


def test_a_mission_without_context_cannot_be_launched(client, db):
    path, _ = db
    repo = MissionRepository(connect(path))
    bare = repo.create_mission("Sans contexte", [])
    assert client.get(f"/api/missions/{bare}").json()["next_step"]["can_pilot"] is False
    assert client.post(f"/api/missions/{bare}/pilote").status_code == 409


def test_unknown_session_is_a_404(client):
    assert client.get("/api/pilote/nope").status_code == 404
    assert client.post("/api/pilote/nope/reponse", json={"prompt_id": 1, "text": ""}).status_code == 404


# --- atelier 1 on the channel: the one real runner whose wiring is ours ---


@pytest.mark.asyncio
async def test_atelier_1_turns_a_model_failure_into_a_clean_block(monkeypatch):
    from ebios_rm.agent_runtime import StructuredCallFailed
    from ebios_rm.api.pilot import WebWorkshop1Runner
    from ebios_rm.orchestrator.signals import WorkshopBlocked
    from ebios_rm.workshops.workshop1_cadrage import agent, workshop

    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    monkeypatch.setattr(agent, "AgnoWorkshop1Runner", lambda: object())

    def failing(*args, **kwargs):
        raise StructuredCallFailed("Provider returned error")

    monkeypatch.setattr(workshop, "run_workshop1", failing)
    runner = WebWorkshop1Runner(object(), MissionRepository(connect(":memory:")), Channel())
    with pytest.raises(WorkshopBlocked, match="Échec du modèle pendant l'atelier 1"):
        await runner.run(MissionContext(organisation_nom="Org", secteur_activite="Santé", applicable_frameworks=["RGPD"], facts=[]), "m1")


@pytest.mark.asyncio
async def test_atelier_1_shows_the_unverified_review_on_the_page_not_on_stdin(monkeypatch):
    from ebios_rm.api.pilot import WebWorkshop1Runner
    from ebios_rm.workshops.workshop1_cadrage import agent, workshop

    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    monkeypatch.setattr(agent, "AgnoWorkshop1Runner", lambda: object())
    monkeypatch.setattr(workshop, "run_workshop1", lambda *a, **k: Workshop1Output())
    channel = Channel()
    runner = WebWorkshop1Runner(object(), MissionRepository(connect(":memory:")), channel)
    seen: list = []
    monkeypatch.setattr(runner._cli, "_review_unverified", lambda repo, mid, out, io_in, io_out: seen.append((io_in, io_out)))

    output = await runner.run(MissionContext(organisation_nom="Org", secteur_activite="Santé", applicable_frameworks=["RGPD"], facts=[]), "m1")

    assert isinstance(output, Workshop1Output)
    assert seen == [(channel.ask, channel.say)]
