"""Instruction text for the Workshop 2 agent (white-box §6, §7, §9, §10, §11, §17).

The system instruction encodes atelier 2's change of perspective: atelier 1 asked
« qu'est-ce qui a de la valeur et sur quoi cela repose ? », atelier 2 asks
« quelles sources de risque sont pertinentes et quels objectifs peuvent-elles
viser ? ». The forbidden confusions of §17 are stated explicitly, and each one is
also enforced in assessment.py — the prompt asks, the code decides.
"""

from __future__ import annotations

import json

from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.plugins.registry import EbiosBase
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Input

SYSTEM_INSTRUCTIONS = """\
Tu es un assistant méthodologique EBIOS Risk Manager dédié exclusivement à l'Atelier 2 (Sources de risque et Objectifs visés). L'utilisateur humain valide tes propositions et garde le contrôle décisionnel.

---

### 1. DÉFINITIONS ET NATURE DES OBJETS (RÈGLES ABSOLUES)
* **Source de risque (SR) :** Représente exclusivement une CATÉGORIE D'ACTEUR MOTIVÉ (ex. : cybercriminel, concurrent, État, employé mécontent). 
  * *Interdiction :* Un équipement (serveur, base de données, annuaire), une vulnérabilité ou un vecteur/technique d'attaque (phishing, injection SQL) n'est JAMAIS une source de risque.
* **Objectif visé (OV) :** Représente uniquement une FINALITÉ STRATÉGIQUE (ex. : espionner, entraver le service, extorquer des fonds, se venger).
  * *Interdiction :* Les modalités ou outils techniques (« PowerShell », « vol d'identifiants ») ne sont JAMAIS des objectifs visés.
* **Biens supports :** Un bien support ne devient pas automatiquement une source de risque ni un objectif visé.

---

### 2. UTILISATION DU RÉFÉRENTIEL ET DU CONTEXTE
* **Strict respect de la base :** Tu choisis UNIQUEMENT parmi les catégories d'acteurs et les finalités définies dans la base méthodologique fournie. Aucune création ou modification de libellé n'est autorisée.
* **Plausibilité & Sélectivité :** Ne retiens pas une catégorie simplement parce qu'elle existe dans la base. Tu dois sélectionner les combinaisons les plus cohérentes et plausibles pour l'organisation étudiée. Ne génère pas toutes les combinaisons théoriques.
* **Justification factuelle obligatoire :**
  * Toute justification doit s'appuyer exclusivement sur des faits réels et explicites décrits dans le contexte fourni.
  * Les justifications génériques, théoriques ou creuses (ex. : "La menace existe toujours", "Tout le monde est cible") sont FORMELLEMENT INTERDITES.
* **Traçabilité stricte (`derived_from_fact_fields`) :**
  * Tu dois citer le nom exact des champs de contexte exploités dans le paramètre `derived_from_fact_fields`.
  * TOUT champ cité doit figurer STRICTEMENT et MOT À MOT dans la liste des clés de contexte fournies dans le prompt. Il est interdit d'inventer, d'altérer ou d'isoler des clés absentes.

---

### 3. COTATIONS ET CALCULS
* **Cotations :** Les cotations demandées sont obligatoirement des entiers compris entre 1 et 4.
* **Interdiction :** N'invente aucun score, aucune échelle personnalisée, ni aucune formule de calcul. La pertinence globale ne t'appartient pas et sera calculée en dehors.

---

### 4. FORMAT STRICT DE RÉPONSE
* Ta réponse doit être EXCLUSIVEMENT un flux JSON valide respectant le schéma attendu.
* **ZÉRO texte hors JSON :** Aucune phrase d'introduction, aucun commentaire, aucun texte d'accompagnement, aucune formule de politesse.
* **ZÉRO balise de code Markdown :** Ne commence PAS par ```json ou ``` et ne termine PAS par ```. 
* Le premier caractère de ta réponse doit être `{` ou `[` et le dernier caractère doit être `}` ou `]`.
"""


def _context_block(w2_input: Workshop2Input) -> str:
    """The organisational context atelier 2 is allowed to see (white-box §3)."""
    return json.dumps(
        {
            "organisation_nom": w2_input.organisation_nom,
            "secteur_activite": w2_input.secteur_activite,
            "contexte": w2_input.contexte,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _atelier1_block(w2_input: Workshop2Input) -> str:
    """Atelier 1's result. Support assets travel as dependency information only (§3, §12)."""
    return json.dumps(
        {
            "biens_essentiels": [
                {
                    "id": a.id, "nom": a.nom, "description": a.description,
                    "nature": a.nature, "processus_metier_associes": a.processus_metier_associes,
                }
                for a in w2_input.biens_essentiels
            ],
            "evenements_redoutes": [
                {
                    "id": e.id, "description": e.description,
                    "bien_essentiel_id": e.bien_essentiel_id,
                    "categorie_impact": e.categorie_impact.value,
                    "gravite": e.gravite.value,
                }
                for e in w2_input.evenements_redoutes
            ],
            "biens_supports_pour_dependances_seulement": [
                {
                    "id": s.id, "nom": s.nom, "type_support": s.type_support,
                    "biens_essentiels_supportes": s.biens_essentiels_supportes,
                }
                for s in w2_input.biens_supports
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _sources_base_block(base: EbiosBase) -> str:
    return json.dumps(
        [
            {
                "categorie_id": c.id, "libelle": c.libelle, "definition": c.definition,
                "indices_de_pertinence": c.indices_pertinence,
            }
            for c in base.sources_risque
        ],
        ensure_ascii=False, indent=2,
    )


def _finalites_base_block(base: EbiosBase) -> str:
    return json.dumps(
        [
            {"finalite_id": f.id, "libelle": f.libelle, "definition": f.definition,
             "exemples": f.exemples}
            for f in base.objectifs_vises
        ],
        ensure_ascii=False, indent=2,
    )


def _revision_block(revision_notes: list[str] | None) -> str:
    """The auditor's rejection reasons, injected only on a redo."""
    if not revision_notes:
        return ""
    joined = "\n".join(f"- {note}" for note in revision_notes if note and note.strip())
    if not joined:
        return ""
    return (
        "\n\nREMARQUES DE L'AUDITEUR SUR LA OU LES VERSIONS PRÉCÉDENTES (à corriger "
        "impérativement dans cette nouvelle proposition) :\n" + joined + "\n"
    )


def _known_fields(w2_input: Workshop2Input) -> str:
    """The exact field names the model may cite — nothing else exists to cite."""
    return json.dumps(sorted(w2_input.contexte.keys()), ensure_ascii=False)


def sources_prompt(w2_input: Workshop2Input, base: EbiosBase,
                   revision_notes: list[str] | None = None) -> str:
    return (
        "Parmi les catégories de sources de risque de la base méthodologique ci-dessous, "
        "lesquelles sont plausibles pour CETTE organisation, dans CE périmètre ?\n"
        "Pour chacune que tu proposes : reprends son categorie_id tel quel, donne un nom "
        "contextualisé (l'acteur tel qu'il se présenterait ici), sa motivation dans ce "
        "contexte, un statut ('retenu' si clairement plausible, 'secondaire' si plausible "
        "mais marginale, 'ecarte' si tu l'examines et la rejettes), une justification "
        "appuyée sur le contexte, et les champs de contexte utilisés dans "
        f"derived_from_fact_fields (uniquement parmi : {_known_fields(w2_input)}).\n"
        "Écarter explicitement une catégorie est un résultat utile : garde-la avec sa "
        "raison plutôt que de l'omettre."
        + _revision_block(revision_notes)
        + f"\n\nBASE MÉTHODOLOGIQUE — CATÉGORIES DE SOURCES DE RISQUE:\n{_sources_base_block(base)}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w2_input)}"
        + f"\n\nRÉSULTAT DE L'ATELIER 1:\n{_atelier1_block(w2_input)}"
    )


def objectifs_prompt(w2_input: Workshop2Input, base: EbiosBase, sources: list[RiskSource],
                     revision_notes: list[str] | None = None) -> str:
    sources_block = json.dumps(
        [{"id": s.id, "nom": s.nom, "categorie": s.categorie_libelle, "motivation": s.motivation}
         for s in sources],
        ensure_ascii=False, indent=2,
    )
    return (
        "Quels objectifs ces sources de risque pourraient-elles viser dans cette "
        "organisation ?\n"
        "Raisonne selon la chaîne : valeur métier -> bien essentiel -> enjeu de sécurité "
        "-> objectif plausible pour une source de risque. Un objectif est une FINALITÉ, "
        "pas une technique.\n"
        "Pour chaque objectif : reprends un finalite_id de la base tel quel, décris "
        "l'objectif en une phrase concrète propre à cette organisation, indique l'enjeu "
        "de l'atelier 1 concerné, la liste des id de biens essentiels visés (ils doivent "
        "exister dans l'atelier 1), un statut, une justification, et les champs de "
        f"contexte utilisés (uniquement parmi : {_known_fields(w2_input)})."
        + _revision_block(revision_notes)
        + f"\n\nBASE MÉTHODOLOGIQUE — FINALITÉS:\n{_finalites_base_block(base)}"
        + f"\n\nSOURCES DE RISQUE RETENUES:\n{sources_block}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w2_input)}"
        + f"\n\nRÉSULTAT DE L'ATELIER 1:\n{_atelier1_block(w2_input)}"
    )

def couples_prompt(
    w2_input: Workshop2Input,
    sources: list[RiskSource],
    objectifs: list[ObjectifVise],
    revision_notes: list[str] | None = None,
) -> str:
    sources_block = json.dumps(
        [{"id": s.id, "nom": s.nom, "categorie": s.categorie_libelle, "motivation": s.motivation} for s in sources],
        ensure_ascii=False,
        indent=2,
    )
    objectifs_block = json.dumps(
        [{"id": o.id, "finalite": o.finalite_libelle, "description": o.description, "biens_essentiels_vises": o.biens_essentiels_vises} for o in objectifs],
        ensure_ascii=False,
        indent=2,
    )
    return (
        "Associe les sources de risque et les objectifs visés qui forment ensemble une "
        "intention cohérente. ÉLIMINE toutes les combinaisons théoriques ou absurdes "
        "qui n'ont aucun sens pratique pour cette organisation au vu du contexte.\n"
        "En revanche, CONSERVE et propose toutes les associations qui sont réellement "
        "logiques, pertinentes et réalistes pour cette organisation. Ne t'impose pas de "
        "limite chiffrée stricte si plusieurs scénarios sont crédibles ; l'auditeur humain "
        "interviendra pour faire le tri final et prioriser si la liste de couples plausibles "
        "est trop longue.\n\n"
        "Veille à ce que chaque couple retenu permette de déclencher de manière logique "
        "au moins un des événements redoutés (ER) listés dans l'Atelier 1 pour les "
        "biens essentiels ciblés par l'objectif.\n\n"
        "Pour chaque couple : source_risque_id, objectif_vise_id, une justification, un "
        "statut ('retenu' ou 'secondaire'), et trois cotations entières de 1 à 4 :\n"
        " - motivation : (1=Opportuniste, 2=Intérêt indirect/rebond, 3=Intérêt direct/lucratif, 4=Cible de choix/déterminé) ;\n"
        " - ressources : (1=Individuelles/Outils publics, 2=Groupe limité/Outils standard, 3=Professionnelles/Moyens cyber, 4=Illimitées/Étatiques) ;\n"
        " - activite : (1=Jamais observée, 2=Faible/Sporadique, 3=Active/Fréquente, 4=Intense/Généralisée dans le secteur).\n"
        "Ne calcule ni pertinence ni vraisemblance : elles sont dérivées de tes cotations."
        + _revision_block(revision_notes)
        + f"\n\nSOURCES DE RISQUE:\n{sources_block}"
        + f"\n\nOBJECTIFS VISÉS:\n{objectifs_block}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w2_input)}"
    )