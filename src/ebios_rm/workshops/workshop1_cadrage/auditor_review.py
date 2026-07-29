"""Expert auditor review — dynamic, professional follow-up questions (conception §2).

§2 lists question-generation as one of the AI's four jobs ("génère des questions"),
not just filling a fixed catalog. This module reads the whole Mission Context after
the catalog pass and proposes real audit-grade follow-ups the way an experienced
EBIOS RM auditor would — grounded in what was actually said (a named EDR with no
version, MFA on some systems but not others, a claimed control with no evidence of
testing), never inventing a new organizational fact.

Runs in rounds so an answer can open a new, deeper question (EDR name -> version ->
patch cadence), same as a real interview. Bounded so it cannot run forever.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Protocol

from pydantic import BaseModel, Field

from ebios_rm.agent_runtime import StructuredCallFailed, facts_as_json, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion

# The review stops when the auditor-agent has nothing further worth asking — that
# is the intended end condition. The two ceilings below are runaway backstops only
# (a model that keeps rewording the same concern forever, or an interrogation that
# never ends), not the normal way the loop terminates.
MAX_ROUNDS = 10
MAX_TOTAL_QUESTIONS = 30
MAX_QUESTIONS_PER_ROUND = 6

_SYSTEM = """\
Tu es un auditeur EBIOS Risk Manager expérimenté qui relit le contexte déjà
recueilli pour une mission, comme le ferait un professionnel senior avant de
lancer les ateliers.

Ta tâche : proposer des questions de suivi PERTINENTES et PRÉCISES, comme le
ferait un vrai auditeur qui creuse une réponse — pas des questions génériques,
et jamais des questions dont la réponse figure déjà dans les faits connus.

ALTITUDE — atelier 1 (cadrage et socle de sécurité) UNIQUEMENT :
Tu cherches de quoi cadrer le périmètre et juger le socle : biens essentiels et
supports, événements redoutés et leur gravité, périmètre, référentiels déclarés,
existence et couverture d'une mesure. Tu t'arrêtes à « la mesure existe-t-elle, sur
quel périmètre, a-t-elle été vérifiée ». Le détail d'ingénierie interne relève des
ateliers 3 et 4 et ne se demande PAS ici : paramètres cryptographiques, rotation de
clés HSM, valeurs d'epsilon en confidentialité différentielle, durcissement d'une
CVE précise, réglages produit. Devant le choix, pose la question de cadrage.

Règles absolues :
- Chaque question doit se justifier par un fait déjà présent (based_on_fact =
  le field_name du fait qui motive la question) OU par une lacune méthodologique
  évidente au regard des référentiels déclarés (based_on_fact vide dans ce cas,
  mais explique pourquoi dans "why").
- Tu ne poses JAMAIS une question qui affirme un fait sur l'organisation ("puisque
  vous avez subi telle attaque...") sauf si ce fait est déjà dans le contexte.
- Tu n'inventes rien : si aucune question pertinente ne vient, réponds avec une
  liste vide.
- Tu ne reposes JAMAIS une question déjà posée (voir QUESTIONS DÉJÀ POSÉES), même
  reformulée, traduite ou abordée sous un autre angle. Si le sujet est couvert,
  passe à autre chose ou renvoie une liste vide.
- Priorité 'critical' seulement si la question bloque une évaluation de sécurité
  essentielle ; sinon 'important'.
- Exemples du niveau de finesse attendu : un EDR est nommé sans version ni
  cadence de mise à jour -> demande-le. Le MFA est confirmé sur certains systèmes
  mais pas mentionné sur un système critique -> demande une confirmation
  explicite. Un contrôle est déclaré sans preuve de test/audit -> demande si et
  quand il a été vérifié.

Réponds uniquement au format structuré demandé.
"""


class AuditorFollowUp(BaseModel):
    """One professional follow-up question, grounded in the existing context (conception §2)."""

    question: str
    why: str                          # methodological justification, shown to the auditor
    priority: str = "important"       # 'critical' | 'important'
    based_on_fact: str = ""           # field_name that triggered this question, if any


class AuditorReviewBatch(BaseModel):
    proposals: list[AuditorFollowUp] = Field(default_factory=list)


class AuditorReviewRunner(Protocol):
    def review(self, mission_context: MissionContext, round_number: int) -> list[AuditorFollowUp]:
        ...


def already_asked(mission_context: MissionContext) -> list[str]:
    """Questions already put to the auditor, read back from the Facts they produced.

    The facts are checkpointed, so this survives a crash: a resumed review knows
    what was asked before it, instead of regenerating a reworded round 1 (the round
    counter itself is per-session and only labels the progress line).
    """
    return [f.question for f in mission_context.facts if f.question]


def _tokens(text: str) -> set[str]:
    """Accent-free lowercase word/number tokens: « Norme ISO 27001 » -> {norme, iso, 27001}."""
    plain = unicodedata.normalize("NFKD", text.casefold())
    return set(re.findall(r"[a-z]+|\d+", "".join(c for c in plain if not unicodedata.combining(c))))


def _make_field_name(question: str) -> str:
    """Stable id derived by hashing the question text, matching the gap_id pattern elsewhere.

    Hashed on the sorted accent-free word set, not the raw string: the prompt asks the
    model not to repeat a question "même reformulée", but that is only a request. The
    id makes a question that differs solely in case, accents, punctuation or word order
    collide with the one already asked, so the ``asked`` filter drops it in code.
    Genuinely new wording still gets through — that part stays the model's job.
    """
    digest = hashlib.sha256(" ".join(sorted(_tokens(question))).encode("utf-8")).hexdigest()
    return f"AUD-{digest[:8]}"


def to_followup_question(proposal: AuditorFollowUp) -> FollowUpQuestion:
    priority = PriorityLevel.CRITICAL if proposal.priority == "critical" else PriorityLevel.IMPORTANT
    # The fact that motivated the question is shown to the auditor, who can then see
    # whether it is grounded in the dossier or in nothing. Collected and dropped, it
    # was a rule the model was asked to follow with no consequence either way.
    why = f"{proposal.why} (à partir de « {proposal.based_on_fact} »)" if proposal.based_on_fact else proposal.why
    return FollowUpQuestion(_make_field_name(proposal.question), proposal.question, priority, why)


def grounded(proposals: list[AuditorFollowUp], mission_context: MissionContext) -> list[AuditorFollowUp]:
    """Drop proposals citing a fact that does not exist (conception §2).

    A question may rest on a named fact, or on a methodological gap in the declared
    referentials (based_on_fact empty, justified in `why`). What it may not do is cite
    a fact nobody ever recorded: that is the model inventing its own justification, and
    the auditor has no way to tell from the question text alone.
    """
    known = {f.field_name for f in mission_context.facts}
    return [p for p in proposals if not p.based_on_fact or p.based_on_fact in known]


class AgnoAuditorReviewRunner:
    """Concrete AuditorReviewRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0, progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def review(self, mission_context: MissionContext, round_number: int) -> list[AuditorFollowUp]:
        from agno.agent import Agent  # noqa: PLC0415

        asked = already_asked(mission_context)
        prompt = (
            f"RÉFÉRENTIELS DÉCLARÉS : {mission_context.applicable_frameworks}\n"
            f"FAITS CONNUS : {facts_as_json(mission_context.facts)}\n"
            "QUESTIONS DÉJÀ POSÉES (ne les repose pas, même reformulées) :\n"
            + ("\n".join(f"- {q}" for q in asked) or "- (aucune)")
            + f"\n\nPropose jusqu'à {MAX_QUESTIONS_PER_ROUND} questions de suivi professionnelles "
            "NOUVELLES, ou une liste vide s'il n'y a plus rien de pertinent à demander."
        )
        try:
            batch = run_structured(
                lambda: Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=AuditorReviewBatch, markdown=False),
                prompt, AuditorReviewBatch,
                what=f"relecture experte (round {round_number}/{MAX_ROUNDS})",
                max_attempts=self._max_attempts, base_delay=self._base_delay, progress=self._progress,
            )
        except StructuredCallFailed as exc:
            # A failed review round is not a methodology outcome: no proposals, never invented.
            self._progress(f"   (relecture experte indisponible ce round : {str(exc)[:120]})")
            return []
        return grounded(batch.proposals, mission_context)[:MAX_QUESTIONS_PER_ROUND]
