"""The atelier 5 session — what only the organisation can answer before a plan is written.

The method puts Direction, Métiers, RSSI and DSI around the table for atelier 5, and
four things come from them, not from an agent: where the acceptance threshold sits, what
means exist to treat, who will carry the measures, and how often the committee will look
at them. Without these the plan is a wish list with no owner and no date.

Four questions, each feeding one activity: 5-2 (threshold), 5-3 (means and owners),
5-5 (committee). Asked through the shared session mechanics — only what the dossier
does not already answer, none of them blocking, a skip kept with its reason (§8).
"""

from __future__ import annotations

from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.mission_context.session import SessionQuestion, ask_questions, pending_questions
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface
from ebios_rm.workshops.workshop5_traitement_risque.models import Workshop5Input

SESSION_QUESTIONS: tuple[SessionQuestion, ...] = (
    SessionQuestion(
        "seuil_acceptation_risque",
        "À partir de quel niveau un risque devient-il inacceptable pour votre direction, "
        "et qui prononce cette décision ?",
        "C'est le seuil qui sépare ce qui doit être traité à court terme de ce qui est suivi : "
        "sans lui, c'est l'agent qui le fixerait à votre place.",
    ),
    SessionQuestion(
        "moyens_traitement",
        "De quels moyens disposez-vous pour traiter les risques cette année : budget, "
        "charge interne, prestataires ?",
        "Un plan calibré au-dessus de vos moyens n'est pas mis en œuvre ; il faut le savoir "
        "avant de le rédiger.",
    ),
    SessionQuestion(
        "responsables_mesures",
        "Qui portera les mesures selon leur nature : gouvernance, technique, juridique, continuité ?",
        "Le plan de traitement nomme un responsable par mesure ; ce sont vos rôles réels, pas des rôles types.",
    ),
    SessionQuestion(
        "cadence_comite_securite",
        "À quelle fréquence une instance peut-elle examiner l'avancement du plan et l'évolution "
        "des risques ?",
        "Le cadre de suivi de l'atelier 5 s'appuie sur cette instance ; la méthode suggère tous les "
        "six mois en montée en puissance, tous les douze en rythme de croisière.",
    ),
)


def session_questions(w5_input: Workshop5Input) -> list[FollowUpQuestion]:
    """The atelier 5 session questions the context does not already answer."""
    return pending_questions(SESSION_QUESTIONS, w5_input)


def ask_session_questions(w5_input: Workshop5Input, human: HumanInterface) -> Workshop5Input:
    """Run the atelier 5 session and return the enriched input."""
    return ask_questions(SESSION_QUESTIONS, w5_input, human)
