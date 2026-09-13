"""The atelier 3 session with the client — who is already inside the perimeter.

Atelier 3 asks by which route a source de risque would arrive, and the most
frequent route is a party the organisation itself let in: a provider with a
permanent link, a subcontractor holding the data, a remote-access channel. If the
dossier does not name them, the agent has nothing to route through and can only
propose direct attacks — so the questions below are put in session before the
workshop runs, and only the ones the context does not already answer.

Five questions, each one there to make a route describable rather than guessed.
They are authored, not sourced: the conception document specifies the count gate
of §17 in detail and says nothing about an ecosystem interview. Treat them as
usable and unvalidated, like atelier 2's.

The mechanics are shared (mission_context/session.py): asked through an injected
HumanInterface so a scripted human can drive them in tests, never an LLM call —
which questions are missing is a lookup, and a model asking them would only add a
way to invent one. None of them blocks; a skip keeps its justification (§8) and is
not asked again.
"""

from __future__ import annotations

from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.mission_context.session import SessionQuestion, ask_questions, pending_questions
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Input

# Ordered as a conversation: who is connected, who holds the data, what the
# contracts require of them, and how anyone reaches the inside from outside.
SESSION_QUESTIONS: tuple[SessionQuestion, ...] = (
    SessionQuestion(
        "interconnexions_tiers",
        "Quelles liaisons permanentes avez-vous avec des partenaires ou des prestataires ?",
        "Une liaison ouverte en continu est un chemin d'entrée qui ne passe pas par votre porte.",
    ),
    SessionQuestion(
        "sous_traitants_donnees",
        "Qui traite ou héberge vos données pour votre compte ?",
        "Un tiers qui détient vos données peut être visé à votre place.",
    ),
    SessionQuestion(
        "fournisseurs_cloud",
        "Quels services en ligne ou cloud utilisez-vous pour votre activité ?",
        "Ils étendent la surface de l'étude à des acteurs que vous n'administrez pas.",
    ),
    SessionQuestion(
        "clauses_securite_contrats",
        "Vos contrats avec ces tiers imposent-ils des exigences de sécurité ?",
        "Sans exigence contractuelle, rien n'oblige un tiers à vous prévenir ni à se protéger.",
    ),
    SessionQuestion(
        "acces_distant_moyens",
        "Par quels moyens vos équipes et vos prestataires accèdent-ils au système à distance ?",
        "C'est le chemin par lequel un accès légitime devient un accès emprunté.",
    ),
)


def session_questions(w3_input: Workshop3Input) -> list[FollowUpQuestion]:
    """The atelier 3 session questions the context does not already answer."""
    return pending_questions(SESSION_QUESTIONS, w3_input)


def ask_session_questions(w3_input: Workshop3Input, human: HumanInterface) -> Workshop3Input:
    """Run the atelier 3 session and return the enriched input."""
    return ask_questions(SESSION_QUESTIONS, w3_input, human)
