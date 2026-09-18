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
Tu es un assistant méthodologique EBIOS Risk Manager dédié exclusivement à l'Atelier 2 (Sources de risque et Objectifs visés). L'utilisateur humain valide tes propositions et garde le contrôle décisionnel : tu proposes et tu argumentes, un auditeur décide.

Tes propositions passent ensuite par un filtre automatique strict. Ce qui enfreint une règle ci-dessous n'est pas corrigé : c'est supprimé, avec son motif de rejet.

---

### 1. DÉFINITIONS ET NATURE DES OBJETS (RÈGLES ABSOLUES)
* **Source de risque (SR) :** Représente exclusivement une CATÉGORIE D'ACTEUR MOTIVÉ (ex. : cybercriminel, concurrent, État, employé mécontent). 
  * *Interdiction :* Un équipement (serveur, base de données, annuaire, réseau), une vulnérabilité ou un vecteur/technique d'attaque (phishing, injection SQL, rançongiciel, déni de service) n'est JAMAIS une source de risque.
* **Objectif visé (OV) :** Représente uniquement une FINALITÉ STRATÉGIQUE (ex. : espionner, entraver le service, extorquer des fonds, se venger).
  * *Interdiction :* Les modalités, outils ou techniques (« PowerShell », « vol d'identifiants », « hameçonnage ») ne sont JAMAIS des objectifs visés. Décris QUI agit et ce qu'il veut, jamais comment il s'y prend.
* **Biens supports :** Un bien support ne devient pas automatiquement une source de risque ni un objectif visé.

---

### 2. UTILISATION DU RÉFÉRENTIEL ET DU CONTEXTE
* **Strict respect de la base :** Tu choisis UNIQUEMENT parmi les catégories d'acteurs et les finalités définies dans la base méthodologique fournie, en reprenant leur identifiant tel quel. Aucune création ou modification n'est tolérée.
* **Plausibilité & Sélectivité :** Ne retiens pas une catégorie simplement parce qu'elle existe dans la base. Tu dois sélectionner les combinaisons les plus cohérentes et plausibles pour l'organisation étudiée. Si rien n'est plausible, tu renvoies une liste vide.
* **Justification factuelle obligatoire :**
  * Toute justification doit s'appuyer exclusivement sur des faits réels et explicites décrits dans le contexte fourni. Les justifications génériques (ex. : "La menace existe toujours") sont FORMELLEMENT INTERDITES.
  * **Règle d'or :** Tu écris la justification AVANT de conclure sur le statut (le raisonnement précède le verdict).
* **Traçabilité stricte (`derived_from_fact_fields`) :**
  * Tu dois citer le nom exact des champs de contexte exploités dans le paramètre `derived_from_fact_fields`.
  * TOUT champ cité doit figurer STRICTEMENT et MOT À MOT dans la liste des clés de contexte fournies.

---

### 3. COTATIONS ET STATUTS
* **Cotations :** Les cotations demandées sont obligatoirement des entiers compris entre 1 et 4. N'invente aucun score, échelle personnalisée ou formule.
* **Statuts :** Le champ statut vaut exactement 'retenu', 'secondaire' ou 'ecarte' ; toute autre valeur fait écarter l'élément.

---

### 4. FORMAT STRICT DE RÉPONSE
* Ta réponse doit être EXCLUSIVEMENT un flux JSON valide respectant le schéma attendu.
* **ZÉRO texte hors JSON :** Aucune phrase d'introduction, aucun commentaire, aucune formule de politesse.
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
    # finalites_typiques travels with the category: the quality checker warns on a
    # couple whose finalité is not typical of its actor, so the model is shown the
    # same table it will be judged against instead of guessing at it.
    return json.dumps(
        [
            {
                "categorie_id": c.id, "libelle": c.libelle, "definition": c.definition,
                "indices_de_pertinence": c.indices_pertinence,
                "finalites_typiques": c.finalites_typiques,
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
        "Procède catégorie par catégorie : confronte ses indices_de_pertinence au "
        "contexte, écris la justification, puis conclus par le statut.\n"
        "Pour chaque catégorie que tu examines :\n"
        "  - categorie_id : repris tel quel depuis la base ;\n"
        "  - nom : l'acteur tel qu'il se présenterait ici, sans nommer ni technique "
        "d'attaque ni bien support ;\n"
        "  - motivation : ce qu'il chercherait dans CE contexte ;\n"
        "  - justification : le raisonnement, appuyé sur des éléments du contexte ;\n"
        "  - derived_from_fact_fields : au moins un champ, uniquement parmi : "
        f"{_known_fields(w2_input)} ;\n"
        "  - statut : 'retenu' si clairement plausible, 'secondaire' si plausible mais "
        "marginale, 'ecarte' si tu l'examines et la rejettes.\n"
        "Sois sélectif : en pratique 3 à 6 catégories retenues. Écarter explicitement "
        "une catégorie est un résultat utile : garde-la avec sa raison plutôt que de "
        "l'omettre."
        + _revision_block(revision_notes)
        + f"\n\nBASE MÉTHODOLOGIQUE — CATÉGORIES DE SOURCES DE RISQUE:\n{_sources_base_block(base)}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w2_input)}"
        + f"\n\nRÉSULTAT DE L'ATELIER 1:\n{_atelier1_block(w2_input)}"
    )


def objectifs_prompt(w2_input: Workshop2Input, base: EbiosBase, sources: list[RiskSource],
                     revision_notes: list[str] | None = None) -> str:
    sources_block = json.dumps(
        [{"id": s.id, "nom": s.nom, "categorie": s.categorie_libelle,
          "categorie_id": s.categorie_id, "motivation": s.motivation}
         for s in sources],
        ensure_ascii=False, indent=2,
    )
    known_be = json.dumps(
        [{"id": a.id, "nom": a.nom} for a in w2_input.biens_essentiels], ensure_ascii=False
    )
    return (
        "Quels objectifs ces sources de risque pourraient-elles viser dans cette "
        "organisation ?\n"
        "Raisonne selon la chaîne : valeur métier -> bien essentiel -> enjeu de sécurité "
        "-> objectif plausible pour une source de risque. Un objectif est une FINALITÉ, "
        "pas une technique : « obtenir une rançon » est un objectif, « rançongiciel » "
        "n'en est pas un.\n"
        "Pour chaque objectif :\n"
        "  - finalite_id : repris tel quel depuis la base ;\n"
        "  - description : l'objectif en une phrase concrète propre à cette "
        "organisation, sans nommer de technique ;\n"
        "  - enjeu : l'enjeu de sécurité de l'atelier 1 concerné ;\n"
        f"  - biens_essentiels_vises : au moins un id pris dans {known_be} ; un objectif "
        "qui ne vise aucun bien essentiel connu est supprimé ;\n"
        "  - justification, puis statut ('retenu', 'secondaire' ou 'ecarte') ;\n"
        "  - derived_from_fact_fields : au moins un champ, uniquement parmi : "
        f"{_known_fields(w2_input)}.\n"
        "Reste sélectif : un à trois objectifs par source retenue suffisent en général, "
        "et deux formulations du même objectif comptent pour une."
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
        "intention cohérente. NE PRODUIS PAS toutes les combinaisons : ne garde que "
        "celles qui ont un sens pour cette organisation — un acteur ne poursuit pas "
        "n'importe quelle finalité, et une finalité inhabituelle pour cet acteur doit "
        "être argumentée dans la justification.\n"
        "N'emploie que les id listés ci-dessous : un couple citant un id absent de ces "
        "listes est supprimé.\n\n"
        "Veille à ce que chaque couple retenu permette de déclencher de manière logique "
        "au moins un des événements redoutés (ER) listés dans l'Atelier 1 pour les "
        "biens essentiels ciblés par l'objectif.\n\n"
        "Pour chaque couple : source_risque_id, objectif_vise_id, une justification, un "
        "statut ('retenu' ou 'secondaire'), et trois cotations entières de 1 à 4 "
        "(une cotation hors de 1..4, ou absente, fait supprimer le couple) :\n"
        "  - motivation : (1=Opportuniste, 2=Intérêt indirect/rebond, 3=Intérêt direct/lucratif, 4=Cible de choix/déterminé) ;\n"
        "  - ressources : (1=Individuelles/Outils publics, 2=Groupe limité/Outils standard, 3=Professionnelles/Moyens cyber, 4=Illimitées/Étatiques) ;\n"
        "  - activite : (1=Jamais observée, 2=Faible/Sporadique, 3=Active/Fréquente, 4=Intense/Généralisée dans le secteur).\n"
        "Ne calcule ni pertinence ni vraisemblance : elles sont dérivées de tes cotations."
        + _revision_block(revision_notes)
        + f"\n\nSOURCES DE RISQUE:\n{sources_block}"
        + f"\n\nOBJECTIFS VISÉS:\n{objectifs_block}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w2_input)}"
    )