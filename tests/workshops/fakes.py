"""Test doubles for Workshop 1 — a scripted HumanInterface and a fake agent runner,
so the full orchestration runs deterministically without stdin or any LLM."""

from __future__ import annotations

from ebios_rm.domain.enums import CategorieImpact, Gravite, Origin
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.mission_context.clarification import ClarificationAnswer
from ebios_rm.mission_context.ingestion import ExtractedAnswer
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.mission_context.questionnaire import Question
from ebios_rm.mission_context.validation import Contradiction
from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage.agent_runner import LegalImpactAssignment
from ebios_rm.workshops.workshop1_cadrage.human_interface import SkipRequested
from ebios_rm.workshops.workshop1_cadrage.models import (
    CadrageProposal,
    ControlAssessmentProposal,
)
from ebios_rm.workshops.workshop2_sources_risque.models import (
    CoupleProposal,
    ObjectifViseProposal,
    RiskSourceProposal,
)


class ScriptedHuman:
    """Answers follow-ups/confirmations/contradictions from pre-set scripts."""

    # Derived answers are accepted wholesale unless a test overrides this.
    def confirm_derived_answers(self, reviews):
        return list(reviews)

    def __init__(
        self,
        answers: dict[str, str] | None = None,
        skips: dict[str, str] | None = None,
        confirmations: dict[str, bool] | None = None,
        resolutions: dict[str, object] | None = None,
        flag_decisions: dict[str, object] | None = None,
    ) -> None:
        self.answers = answers or {}
        self.skips = skips or {}
        self.confirmations = confirmations or {}
        self.resolutions = resolutions or {}
        # question_id -> corrected value, or None to discard; absent = keep as-is
        self.flag_decisions = flag_decisions or {}
        self.asked: list[str] = []
        self.reviewed: list[str] = []

    def ask_followup(self, question: FollowUpQuestion):
        self.asked.append(question.field_name)
        if question.field_name in self.skips:
            return SkipRequested(self.skips[question.field_name])
        # Default: answer Critical questions so the flow never blocks in tests.
        return self.answers.get(question.field_name, "réponse de test")

    def confirm_document_only(self, field_name: str, value: object, source_quote: str) -> bool:
        return self.confirmations.get(field_name, True)

    def resolve_contradiction(self, contradiction: Contradiction):
        return self.resolutions.get(contradiction.field_name, contradiction.declaration.value)

    def review_flag(self, flag):
        self.reviewed.append(flag.question_id)
        # Default: keep the answer as-is unless a decision is scripted.
        return self.flag_decisions.get(flag.question_id, flag.answer)


class FakeIngestionRunner:
    """An IngestionRunner that returns canned extracted answers — no LLM involved."""

    def __init__(
        self,
        questionnaire_answers: list[ExtractedAnswer] | None = None,
        supporting_answers: list[ExtractedAnswer] | None = None,
    ) -> None:
        self._q = questionnaire_answers or []
        self._s = supporting_answers or []

    def extract_questionnaire(self, doc_text: str, questions: list[Question]) -> list[ExtractedAnswer]:
        return list(self._q)

    def extract_supporting(self, doc_text: str, doc_name: str, questions: list[Question]) -> list[ExtractedAnswer]:
        return list(self._s)


class FakeClarificationRunner:
    """A ClarificationRunner that answers from the mission context deterministically — no LLM.

    Grounding rule mimicked: if a fact whose field_name is mentioned in the question
    exists, answer from it; otherwise return answered=false (not in context).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def answer(self, question, mission_context, workshop_output=None) -> ClarificationAnswer:
        self.calls.append(question)
        q = question.casefold()
        for fact in mission_context.facts:
            if fact.field_name.casefold() in q and fact.value not in (None, ""):
                return ClarificationAnswer(
                    answered=True,
                    answer=f"{fact.field_name} = {fact.value}",
                    based_on_facts=[fact.field_name],
                )
        return ClarificationAnswer(
            answered=False, answer="Information absente du contexte de la mission.",
        )


class FakeRunner:
    """A Workshop1AgentRunner that returns canned proposals — no LLM involved."""

    def __init__(self, gap_control_id: str = "ANSSI-H-21") -> None:
        self.gap_control_id = gap_control_id
        self.revision_notes_seen: list[str] | None = None

    def propose_cadrage(self, mission_context: MissionContext, revision_notes=None) -> CadrageProposal:
        self.revision_notes_seen = revision_notes
        return CadrageProposal(
            biens_essentiels=[
                EssentialAsset(
                    id="BE-1", nom="Dossier patient", description="Données de santé des patients",
                    nature="information", origin=Origin.ASSESSMENT,
                    derived_from_fact_fields=["processus_metier_critiques"],
                )
            ],
            biens_supports=[
                SupportAsset(
                    id="BS-1", nom="SIH", description="Système d'information hospitalier",
                    type_support="application", biens_essentiels_supportes=["BE-1"],
                    origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"],
                )
            ],
            evenements_redoutes=[
                FearedEvent(
                    id="ER-1", description="Divulgation des données de santé", bien_essentiel_id="BE-1",
                    categorie_impact=CategorieImpact.VIE_PRIVEE_PERSONNES_CONCERNEES,
                    gravite=Gravite.CRITIQUE, origin=Origin.ASSESSMENT,
                    derived_from_fact_fields=["donnees_personnelles_traitees"],
                )
            ],
        )

    def assess_controls(self, mission_context, framework, controls, revision_notes=None):
        out: list[ControlAssessmentProposal] = []
        for c in controls:
            if c.control_id == self.gap_control_id:
                out.append(ControlAssessmentProposal(
                    control_id=c.control_id, verdict="gap",
                    evidence_quote="acces_distant_moyens = ['VPN'] (pas de MFA mentionné)",
                    weakness="Pas de MFA sur l'accès distant VPN", confidence="high",
                ))
            else:
                out.append(ControlAssessmentProposal(
                    control_id=c.control_id, verdict="insufficient_information",
                    evidence_quote="", confidence="low",
                ))
        return out

    def assess_legal_impacts(self, mission_context, events, provisions, revision_notes=None, assets=None):
        if not events or not provisions:
            return []
        return [
            LegalImpactAssignment(
                evenement_id=events[0].id,
                provision_control_id=provisions[0].control_id,
                evidence_mission_context="donnees_personnelles_traitees = True (données de santé)",
            )
        ]


class FakeWorkshop2Runner:
    """A Workshop2AgentRunner returning canned proposals — no LLM involved.

    Deliberately mixes valid candidates with the failures the real model produces:
    a category outside the approved base, an "objective" that is really a
    technique, and a couple with no usable rating.
    """

    def __init__(self) -> None:
        self.revision_notes_seen: list[str] | None = None
        self.calls: list[str] = []

    def propose_sources(self, w2_input, base, revision_notes=None) -> list[RiskSourceProposal]:
        self.calls.append("sources")
        self.revision_notes_seen = revision_notes
        return [
            RiskSourceProposal(
                categorie_id="crime_organise",
                nom="Groupe cybercriminel organisé",
                description="Acteur lucratif ciblant les établissements de santé.",
                motivation="Monnayer l'arrêt de l'activité et les données de santé.",
                statut="retenu",
                justification="Secteur santé fortement ciblé et forte dépendance à la disponibilité.",
                derived_from_fact_fields=["exposition_internet", "sources_menace_percues"],
            ),
            RiskSourceProposal(
                categorie_id="concurrent",
                nom="Concurrent régional",
                description="Établissement concurrent sur la même zone de recrutement.",
                motivation="Capter des patients et des praticiens.",
                statut="secondaire",
                justification="Concurrence directe citée par le client.",
                derived_from_fact_fields=["concurrence_directe"],
            ),
            # A category the approved base does not define — never invented into an SR (§6).
            RiskSourceProposal(
                categorie_id="apt28",
                nom="APT28",
                statut="retenu",
                justification="Groupe actif contre l'Europe.",
                derived_from_fact_fields=["secteur_activite"],
            ),
        ]

    def propose_objectifs(self, w2_input, base, sources, revision_notes=None) -> list[ObjectifViseProposal]:
        self.calls.append("objectifs")
        return [
            ObjectifViseProposal(
                finalite_id="lucratif",
                description="Obtenir le versement d'une rançon en rendant les dossiers inaccessibles",
                enjeu="Continuité de la prise en charge des patients",
                biens_essentiels_vises=["BE-1"],
                statut="retenu",
                justification="Le client ne peut pas fonctionner sans accès aux dossiers.",
                derived_from_fact_fields=["processus_metier_critiques"],
            ),
            ObjectifViseProposal(
                finalite_id="espionnage",
                description="Capter le fichier des praticiens et leurs conditions",
                enjeu="Avantage concurrentiel",
                biens_essentiels_vises=["BE-1"],
                statut="retenu",
                justification="Information directement exploitable par un concurrent.",
                derived_from_fact_fields=["concurrence_directe"],
            ),
            # A technique dressed up as an objective — forbidden by §9/§17.
            ObjectifViseProposal(
                finalite_id="espionnage",
                description="Injection SQL sur le portail de prise de rendez-vous",
                biens_essentiels_vises=["BE-1"],
                statut="retenu",
                justification="Le portail est exposé.",
                derived_from_fact_fields=["exposition_internet"],
            ),
        ]

    def propose_couples(self, w2_input, sources, objectifs, revision_notes=None) -> list[CoupleProposal]:
        self.calls.append("couples")
        by_finalite = {o.finalite_id: o.id for o in objectifs}
        couples = [
            CoupleProposal(
                source_risque_id=sources[0].id,
                objectif_vise_id=by_finalite["lucratif"],
                justification="Le rançongiciel est le mode d'action lucratif habituel sur ce secteur.",
                motivation=4, ressources=3, activite=4, statut="retenu",
            ),
            CoupleProposal(
                source_risque_id=sources[1].id,
                objectif_vise_id=by_finalite["espionnage"],
                justification="Un concurrent tire un bénéfice direct de ces informations.",
                motivation=3, ressources=2, activite=2, statut="retenu",
            ),
            # No usable rating: cannot be prioritised, and must not be guessed (§17).
            CoupleProposal(
                source_risque_id=sources[0].id,
                objectif_vise_id=by_finalite["espionnage"],
                justification="Possible mais mal caractérisé.",
                motivation=0, ressources=0, activite=0, statut="retenu",
            ),
        ]
        return couples


class FakeAuditorReviewRunner:
    """An AuditorReviewRunner returning scripted proposals per round — no LLM involved."""

    def __init__(self, proposals_by_round: dict[int, list] | None = None) -> None:
        self.proposals_by_round = proposals_by_round or {}
        self.rounds_seen: list[int] = []

    def review(self, mission_context, round_number):
        self.rounds_seen.append(round_number)
        return list(self.proposals_by_round.get(round_number, []))
