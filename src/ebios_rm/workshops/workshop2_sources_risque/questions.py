"""The atelier 2 session with the client — the one phase with no atelier 1 equivalent.

The white-box spec asks for this phase to exist (§5: "the design must let it
build a working session with the client") but does not enumerate its questions —
unlike the intake questionnaire, whose fields come from questionnaire.py's 90-odd
declared items. SESSION_QUESTIONS below is authored, not sourced: nine questions
chosen because each maps to an indice_pertinence in the approved SR/OV base
(plugins/ebios_bases/anssi_ebios_rm_v1/sources_risque.json) — e.g.
"departs_conflictuels" feeds the plausibility of "interne_malveillant" and
"vengeur". They have not been run past a real client or checked against the
official ANSSI guide. Treat them the same way as the base's
verified_against_official_guide flag: usable, not yet validated.

Two design rules, both deliberate:

* It asks through an injected ``HumanInterface`` — the same Protocol the rest of
  the project uses for auditor decisions — so it is testable with a scripted human.
  scripts/run_workshop2.py wires a CLIHumanInterface into it; the orchestrator can
  swap that for its own driver later without touching this module.
* It is not an LLM call. Which questions are missing is a lookup over the context,
  and a model asking them would only add a way to hallucinate one.

Answers become Facts of origin ``declaration`` so they stay distinguishable from
the AI's own assumptions all the way into the SR/OV justifications (white-box §8).
A skip keeps its mandatory justification (conception §8), and the workshop can run
without any of these — none of them blocks.
"""

from __future__ import annotations

from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.mission_context.session import SessionQuestion, ask_questions, pending_questions
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Input


# Ordered as a conversation, not as a form: who would come for us, how, and then
# the specifics that make particular actor categories plausible or not.
SESSION_QUESTIONS: tuple[SessionQuestion, ...] = (
    SessionQuestion(
        "sources_menace_percues",
        "Selon vous, qui pourrait chercher à vous attaquer, et pourquoi ?",
        "Votre propre lecture compte : elle oriente les catégories de sources de risque examinées.",
    ),
    SessionQuestion(
        "chemin_attaque_probable",
        "Par quel chemin une attaque arriverait-elle le plus probablement ?",
        "Sert à apprécier votre exposition, pas à décrire une technique précise.",
    ),
    SessionQuestion(
        "concurrence_directe",
        "Qui sont vos concurrents directs, et y a-t-il des marchés ou dossiers disputés ?",
        "Détermine si un concurrent — ou une officine agissant pour son compte — est plausible.",
    ),
    SessionQuestion(
        "departs_conflictuels",
        "Y a-t-il eu des départs conflictuels, des litiges ou un climat social tendu ?",
        "Détermine si un interne malveillant ou un vengeur est plausible ici.",
    ),
    SessionQuestion(
        "visibilite_publique",
        "Votre organisation est-elle exposée médiatiquement ou publiquement contestée ?",
        "Détermine si un activiste idéologique ou un profil pathologique est plausible.",
    ),
    SessionQuestion(
        "exposition_internet",
        "Quels services sont accessibles depuis Internet ?",
        "Mesure votre surface d'exposition, donc votre attractivité pour un acteur opportuniste.",
    ),
    SessionQuestion(
        "fournisseurs_tiers_critiques",
        "Quels sont vos fournisseurs et prestataires critiques ?",
        "Un tiers de confiance élargit la liste des acteurs qui vous approchent légitimement.",
    ),
    SessionQuestion(
        "incidents_securite_passes",
        "Avez-vous déjà subi des incidents ou des tentatives notables ?",
        "Un acteur déjà venu est le meilleur indice de pertinence disponible.",
    ),
)


def session_questions(w2_input: Workshop2Input) -> list[FollowUpQuestion]:
    """The atelier 2 session questions the context does not already answer."""
    return pending_questions(SESSION_QUESTIONS, w2_input)


def ask_session_questions(w2_input: Workshop2Input, human: HumanInterface) -> Workshop2Input:
    """Run the atelier 2 session and return the enriched input."""
    return ask_questions(SESSION_QUESTIONS, w2_input, human)
