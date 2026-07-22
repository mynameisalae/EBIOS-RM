**CONCEPTION COMPLÈTE**

**Agent IA d'assistance à la méthode EBIOS Risk Manager**

*Document unique et définitif — architecture, pile technologique, bases
de données, Docker, modèle de provenance, cinq ateliers, reporting, et
stratégie de test*

Ce document remplace et fusionne toute version antérieure. Il constitue
la référence unique du projet, suffisamment détaillée pour être
exploitée directement par un professionnel humain ou par un agent IA
chargé de générer le programme.

Version finale avant démarrage du développement

Table des matières

1\. Introduction

Ce document rassemble l'intégralité des décisions de conception prises
pour le système, sans exception et sans renvoi à un autre fichier. Il
suit une logique unique du début à la fin : principes fondateurs, pile
technologique, modèle de provenance de l'information, bases de données,
déploiement, puis le détail complet de chaque atelier et de l'agent de
reporting, et enfin la liste consolidée des limites résiduelles connues.

Aucun code d'implémentation réel n'est fourni ici — le document contient
des schémas de données, des pseudo-code illustratifs, et des
spécifications de comportement suffisamment précises pour qu'un
développeur ou un agent IA puisse implémenter chaque composant sans
ambiguïté.

2\. Principe directeur

Le système est assisté par IA, jamais piloté par IA. L'IA extrait,
analyse, propose, détecte les contradictions et les informations
manquantes, génère des questions, explique son raisonnement. L'IA
n'invente jamais d'information, ne prend jamais de décision d'audit
finale, n'approuve jamais un atelier elle-même, ne suppose jamais une
information manquante, et n'ignore jamais une contradiction. L'auditeur
a toujours le dernier mot.

3\. Pile technologique

Versions vérifiées à la date de rédaction. Toute version doit être
repointée (pinned) explicitement — jamais de contrainte ouverte ni de
tag flottant.

| **Composant** | **Choix retenu** | **Version de référence** | **Rôle** |
|----|----|----|----|
| Langage | Python | 3.13.x (ligne stable actuelle) | Langage unique du projet |
| Framework agent | Agno | 2.6.x (stable ; la ligne 2.7 est en alpha, à éviter en production) | Construction des agents, orchestration, outils, HITL |
| Runtime de production | AgentOS | Fourni avec Agno 2.6.x | Serveur d'exécution (API FastAPI intégrée) |
| Base de données | SQLite | Intégrée à Python | Base de référence ET base de mission |
| Génération Word | python-docx | 1.2.0 | Rapport de mission et annexe d'audit |
| Conteneurisation | Docker | Image officielle Python, variante slim | Déploiement |

3.1 Pourquoi Agno

- Workflows natifs avec Step, Router, Condition, Loop — l'orchestrateur
  séquentiel, le point de branchement selon N en fin d'atelier 3, et la
  boucle de reprise de l'atelier 4 s'implémentent directement avec ces
  primitives.

- Mécanisme HITL / Approvals natif — l'abstraction ask_human
  s'implémente sur ce mécanisme plutôt que d'être construite de zéro.

- Intégration native d'OpenRouter comme fournisseur de modèle unique —
  changement de modèle par variable d'environnement uniquement, sans
  modifier la logique des agents (modèle gratuit en test, Claude via
  OpenRouter en production ; détail en 3.2).

- Stockage de session sur base SQL fournie par l'utilisateur — la base
  de mission de ce projet s'intègre directement.

- Support du Model Context Protocol (MCP), voie d'extension ouverte si
  besoin futur.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Point d'architecture important</strong></p>
<p>Le fan-out de l'atelier 4 n'utilise PAS la primitive Team d'Agno, qui
implique des agents collaboratifs conscients les uns des autres —
exactement ce que ce projet a rejeté dès la conception de l'atelier 4.
Le fan-out s'implémente comme N instances indépendantes d'Agent
standard, dispatchées en parallèle via asyncio.gather.</p></td>
</tr>
</tbody>
</table>

3.2 Fournisseur de modèle — OpenRouter unique, modèle gratuit en test,
Claude en production

Le projet ne code jamais en dur un modèle ni un fournisseur précis. La
couche Agent (section 10.1) instancie son modèle via une fonction
d'usine unique, elle-même pilotée par variable d'environnement —
exactement le même principe de contrat étroit et d'indirection déjà
appliqué à l'orchestrateur (section 10.2) et aux workshops (section 9).
OpenRouter est l'unique fournisseur utilisé, en test comme en production
; seul l'identifiant de modèle (MODEL_ID) change. Aucun atelier ne
référence directement un fournisseur ou un modèle dans son propre code.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>def get_model(): # seul point du code qui connaît le nom d'un
modèle</p>
<p>return OpenRouter(id=MODEL_ID) # agno.models.openrouter.OpenRouter,
seul fournisseur, test et production</p>
<p># Test : MODEL_ID=google/gemma-4-31b-it:free (gratuit, appels
d'outils supportés — voir note ci-dessous)</p>
<p># Prod : MODEL_ID=anthropic/claude-sonnet-5 (Claude, appelé via
OpenRouter et non via agno.models.anthropic.Claude)</p></td>
</tr>
</tbody>
</table>

Pourquoi un seul fournisseur (OpenRouter) pour les deux environnements

- Un seul point d'intégration (une clé API, une classe de modèle Agno)
  donne accès au catalogue complet d'OpenRouter — modèles gratuits pour
  le test, Claude pour la production — sans jamais avoir à maintenir une
  seconde classe de modèle ni une branche de code selon l'environnement.

- Le développement et les itérations de test se font gratuitement via un
  modèle :free du catalogue OpenRouter, sans jamais toucher au code des
  agents ni à la logique de l'orchestrateur.

- Le passage en production ne consiste qu'à changer MODEL_ID (la
  variable d'environnement injectée au conteneur, section 13.3) — jamais
  une réécriture de prompt, d'agent, de Toolkit, ni un second
  fournisseur à intégrer.

- Conformément à la règle de la section 13.1 (jamais de tag flottant),
  MODEL_ID est toujours un identifiant de modèle explicite et épinglé
  (ex. anthropic/claude-sonnet-5) — jamais un routeur comme
  openrouter/free dont la sélection change d'un run à l'autre, ce qui
  casserait la reproductibilité des fiches de test (sections 15 à 20).

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Point d'architecture important — limites connues à
surveiller</strong></p>
<p>Deux points à surveiller avec ce choix. Premièrement, un modèle
gratuit sélectionné sur OpenRouter n'offre pas nécessairement le même
support fiable des appels d'outils (function calling) qu'un modèle
Anthropic — or plusieurs mécanismes du système en dépendent directement
(assess_control, assess_legal_impact, ask_human, sections 10 et 15) ;
google/gemma-4-31b-it:free est indiqué ici comme point de départ car il
liste la prise en charge des outils, mais doit être revérifié contre les
fiches de test des sections 15 à 20 avant adoption définitive — le
catalogue des modèles gratuits change fréquemment. Aucun modèle Gemini
Flash gratuit n'existait sur OpenRouter au moment de la rédaction ;
gemma en est l'équivalent Google le plus proche. Deuxièmement, faire
transiter la production par OpenRouter (plutôt que par un appel direct à
l'API Anthropic) ajoute un intermédiaire supplémentaire dans le chemin
de données du système — à documenter dans toute analyse relative à la
protection des données du projet, puisque celui-ci traite des
informations de sécurité et des données personnelles au sens RGPD
(section 12.3).</p></td>
</tr>
</tbody>
</table>

4\. Le modèle des trois origines de l'information

Principe fondateur qui structure toute manipulation d'information dans
le système. Il généralise le principe d'évaluation par la preuve déjà
appliqué à assess_control (section 10) à l'ensemble du système.

| **Origine** | **Définition** | **Confiance** | **Présentation obligatoire** |
|----|----|----|----|
| Déclaration | Saisi directement par l'auditeur dans le formulaire d'intake | La plus élevée | Un fait déclaré |
| Extraction | Trouvé par l'IA dans un document fourni (politique de sécurité, schéma réseau, inventaire, rapport précédent...) | Élevée, sous réserve de validation | Une extraction, jamais un fait établi sans validation |
| Évaluation | Raisonné/inféré par l'IA à partir d'autres informations | La plus basse | Une appréciation de l'IA, jamais un fait |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Vocabulaire proscrit</strong></p>
<p>Le terme « IA renseigne / complète » ou toute formulation impliquant
que l'IA invente une information est proscrit. Aucune valeur n'est
jamais produite sans un des trois rattachements ci-dessus.</p></td>
</tr>
</tbody>
</table>

5\. Le modèle Fact

5.1 Structure

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>Fact = {</p>
<p>field_name: str, value: Any,</p>
<p>origin: 'declaration' | 'extraction' | 'assessment',</p>
<p>source_document: str | null,</p>
<p>source_quote: str | null, # OBLIGATOIRE et non vide si origin ==
'extraction'</p>
<p>page: int | null,</p>
<p>assessment_basis: list[str] | null, # obligatoire si origin ==
'assessment'</p>
<p>confidence: 'high' | 'medium' | 'low',</p>
<p>status: voir section 6,</p>
<p>validated_by: str | null, validated_at: str | null,</p>
<p>}</p></td>
</tr>
</tbody>
</table>

5.2 Portée — un Fact uniquement pour ce qui affirme quelque chose sur
l'organisation

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Correction — Sur-application initialement
envisagée</strong></p>
<p>Envelopper systématiquement toute donnée (identifiants internes,
horodatages techniques) dans Fact ajoute un surcoût sans bénéfice et
contredit l'objectif de réduction de tokens (section 16). Règle retenue
: seul un champ qui constitue une affirmation sur l'organisation auditée
(infrastructure, contrôle, historique, politique) devient un Fact. Une
donnée de gestion interne reste une valeur simple.</p></td>
</tr>
</tbody>
</table>

5.3 Correctif — citation source obligatoire

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Correction — Absence de citation exacte initialement
prévue</strong></p>
<p>Le mécanisme d'extraction ne rendait pas obligatoire la citation
exacte du passage source, seule une référence de page était prévue —
insuffisant pour une vérification rapide par l'auditeur, contrairement
au principe déjà appliqué aux citations ATT&amp;CK. source_quote devient
obligatoire et non vide pour tout Fact d'origine extraction. Toute
extraction sans citation est automatiquement invalidée par le code avant
d'atteindre l'auditeur.</p></td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>def validate_extraction(fact):</p>
<p>if fact.origin == 'extraction' and not fact.source_quote.strip():</p>
<p>return False # rejeté automatiquement</p>
<p>return True</p></td>
</tr>
</tbody>
</table>

6\. Cycle de vie des statuts d'un Fact

| **Statut** | **Signification** | **Action humaine** |
|----|----|----|
| Declared | Saisi par l'auditeur | Non |
| Extracted | Trouvé dans un document, avec source_quote | Oui — valider |
| Assessed | Inféré par l'IA à partir d'autres Facts | Oui — valider |
| Contradiction | Sources en désaccord | Oui — résolution obligatoire, jamais automatique |
| Missing | Introuvable | Oui, sauf si non suivi comme Fact (section 5.2) |
| Approved | Validé par l'auditeur | Non |
| Rejected | Rejeté | Oui — remplacement ou justification |
| Skipped | Auditeur choisit de ne pas répondre | Justification obligatoire (section 8) |

Une contradiction n'est jamais résolue automatiquement — les deux
valeurs et leurs origines sont présentées côte à côte, la mission ne
peut avancer sur ce point sans décision humaine explicite.

7\. Matrice de priorité de l'information

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Correction — Suppression du niveau « Optionnel » à
omission silencieuse</strong></p>
<p>La version initialement envisagée comportait un troisième niveau
(Optionnel) permettant de continuer silencieusement sans justification.
Ceci contredit le principe déjà vérifié contre la méthode EBIOS RM
officielle selon lequel toute catégorie non couverte doit être
explicitement exclue avec justification — jamais omise silencieusement.
La matrice est réduite à deux niveaux ; ce qui aurait été « Optionnel »
n'est simplement jamais suivi comme Fact (section 5.2), car sans
conséquence méthodologique.</p></td>
</tr>
</tbody>
</table>

| **Niveau** | **Comportement** | **Exemple** |
|----|----|----|
| Critical | Le workshop ne peut pas continuer sans fourniture ou confirmation explicite | Valeurs métier essentielles (atelier 1) |
| Important | L'IA demande l'information manquante ; Skip/Unknown/Not Applicable acceptés uniquement avec justification non vide | Stratégie de sauvegarde, détail d'un contrôle spécifique |

8\. Justification obligatoire — règle universelle

Toute action qui renvoie du travail à un agent, tout rejet, toute
décision de type Skip, exige un motif non vide avant exécution — sans
exception, quel que soit l'atelier ou le mécanisme concerné.

|  |
|----|
| skip_decision = { status: 'skipped', reason: str } \# reason NON VIDE, obligatoire |

9\. Contrats de workshop étroits

Chaque atelier reçoit un modèle d'entrée typé contenant uniquement les
champs dont il a méthodologiquement besoin — jamais la sortie complète
de l'atelier précédent transmise telle quelle.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p># Rejeté : def run_workshop_2(w1_output: dict): ...</p>
<p># Retenu :</p>
<p>class Workshop2Input(TypedModel):</p>
<p>essential_assets: list[EssentialAsset]</p>
<p>feared_events: list[FearedEvent]</p>
<p>def run_workshop_2(input: Workshop2Input): ...</p></td>
</tr>
</tbody>
</table>

Ce principe généralise la règle déjà appliquée aux écarts du socle
transmis à l'atelier 4 (section 15, stripés de toute référence de
framework).

10\. Architecture en couches et orchestrateur

10.1 Couches

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>Agent → raisonne, appelle des outils, produit des
propositions</p>
<p>↓</p>
<p>Business Service → implémente la logique méthodologique EBIOS RM</p>
<p>↓</p>
<p>Repository → accès aux données, aucune logique métier</p>
<p>↓</p>
<p>SQLite → les deux bases (section 12)</p>
<p>↓</p>
<p>Toolkit → fonctions d'interrogation ATT&amp;CK et conformité</p></td>
</tr>
</tbody>
</table>

10.2 Orchestrateur — règle absolue

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>Atelier N → Mission State → Orchestrateur → Atelier N+1</p>
<p># jamais d'appel direct Atelier N → Atelier N+1</p></td>
</tr>
</tbody>
</table>

Cette règle permet, sans mécanisme supplémentaire : pause/reprise à tout
moment, rejeu d'un atelier isolé, historique de versions, insertion des
points de validation humaine sans jamais modifier le code d'un atelier.

11\. Mission Context — source unique de vérité

Aucun atelier n'opère jamais directement sur un PDF, un DOCX, ou le
formulaire brut.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>Formulaire d'intake + Documents fournis</p>
<p>↓</p>
<p>Extraction (source_quote obligatoire)</p>
<p>↓</p>
<p>Validation (3 cas : identique / extraction seule / contradiction)</p>
<p>↓</p>
<p>Mission Context (objet unique, entièrement composé de Facts
validés)</p>
<p>↓</p>
<p>Atelier 1</p></td>
</tr>
</tbody>
</table>

Les trois cas de validation

| **Cas** | **Exemple** | **Résultat** |
|----|----|----|
| Information identique | Formulaire: 'VPN + MFA' / Document: 'VPN + MFA' | Verified, confiance élevée |
| Information en document seul | Formulaire vide / Document: 'CrowdStrike Falcon' | Proposé à l'auditeur pour simple confirmation — aucune question inutile posée si l'évidence est déjà disponible |
| Contradiction | Formulaire: 'Télétravail: Non' / Document: 'Politique VPN' présente | Contradiction signalée, résolution humaine obligatoire |

11.1 Formulaire d'intake standardisé — org_context_form

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Correction — champ nommé sans contenu défini dans les
versions antérieures</strong></p>
<p>Les sections précédentes référençaient déjà org_context_form et le
formulaire d'intake par leur nom (sections 4, 11, 12.4) sans jamais en
définir le contenu réel. Un développeur ou un agent IA ne pouvait donc
pas implémenter ce point sans ambiguïté, contrairement au principe posé
en section 1. Cette section comble ce vide en donnant au formulaire un
schéma concret.</p></td>
</tr>
</tbody>
</table>

Le formulaire d'intake n'est pas une page libre : c'est un fichier
structuré unique, org_context_form, qui pose par avance toutes les
questions génériques communes à toute mission EBIOS RM — le même
formulaire sert de point de départ quel que soit le client. Il donne à
l'agent un socle exploitable dès le lancement de la mission, avant même
qu'un seul échange avec l'auditeur n'ait eu lieu.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>org_context_form = {</p>
<p>organisation_nom: str, secteur_activite: str, taille_effectif:
int,</p>
<p>perimetre_geographique: list[str],</p>
<p>systeme_information_resume: str, # description libre de
l'architecture IT</p>
<p>hebergement: 'sur_site' | 'cloud' | 'hybride',</p>
<p>teletravail_autorise: bool, acces_distant_moyens: list[str], # ex.
VPN, MFA, VDI</p>
<p>edr_av_deploye: str | null, sauvegarde_strategie: str | null,</p>
<p>donnees_personnelles_traitees: bool, categories_donnees_personnelles:
list[str] | null,</p>
<p>incidents_securite_passes: str | null, audits_anterieurs: str |
null,</p>
<p>fournisseurs_tiers_critiques: list[str],</p>
<p>applicable_frameworks: list[str], # section 12.4, pré-rempli
ISO27001/ANSSI_hygiene/RGPD/NIST</p>
<p>processus_metier_critiques: list[str], # amorce pour les biens
essentiels, atelier 1</p>
<p>documents_fournis: list[str] | null, # noms des fichiers joints,
entièrement optionnel</p>
<p>}</p></td>
</tr>
</tbody>
</table>

Liste non exhaustive par construction — c'est le socle générique le plus
complet possible, extensible sans changement d'architecture, à condition
que tout nouveau champ suive la même règle de rattachement (Fact
d'origine 'declaration', section 4).

Fonctionnement

1.  Le formulaire org_context_form est rempli par l'auditeur en amont de
    toute mission ; tout champ renseigné devient un Fact d'origine
    'declaration' (section 4), la confiance la plus élevée.

2.  Des documents peuvent être joints en complément, de façon
    strictement optionnelle (politique de sécurité, schéma réseau,
    inventaire, rapport précédent...) ; ils suivent le pipeline
    d'extraction déjà décrit ci-dessus (Facts d'origine 'extraction',
    source_quote obligatoire).

3.  Une fois le formulaire et les documents éventuels ingérés, l'agent
    applique la Matrice de priorité (section 7) aux champs encore vides
    ou en statut Missing : il ne pose une question à l'auditeur que pour
    les champs Critical (bloquants) et Important (justification exigée
    en cas de Skip) — jamais pour un champ déjà répondu dans le
    formulaire ou confirmé par un document, conformément au principe
    déjà énoncé ci-dessus (« aucune question inutile posée si l'évidence
    est déjà disponible »).

4.  Si le contenu d'un document contredit une réponse du formulaire, ou
    si une valeur semble incohérente au regard d'un autre Fact déjà
    validé, le cas suit exactement la logique des trois cas de
    validation ci-dessus (Contradiction → résolution humaine
    obligatoire, jamais résolue automatiquement) ; l'IA ne suppose
    jamais une information manquante et n'ignore jamais une
    contradiction ou une incohérence (principe directeur, section 2).

5.  Ce formulaire précède et alimente directement le pipeline Mission
    Context décrit ci-dessus ; il n'introduit aucun mécanisme
    supplémentaire — il donne un contenu concret à ce qui n'était, avant
    cette section, qu'un nom de champ
    (org_context_form.applicable_frameworks, section 12.4).

12\. Bases de données

Deux bases SQLite, aucune base vectorielle nulle part — tous les accès
sont relationnels et par identifiant.

| **Base** | **Contenu** | **Nature** |
|----|----|----|
| Référence | Tables ATT&CK + tables de conformité (voir 12.2) | Lecture seule pendant une mission, rafraîchie périodiquement, version figée par mission |
| Mission | mission_state, decision_log, versions, calibrage des coûts | Lecture-écriture continue |

12.1 Schéma — base de référence

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>TABLE attack_techniques(technique_id PK, name, tactic,
description, attck_version)</p>
<p>TABLE attack_mitigations(mitigation_id PK, name, description,
applies_to_technique_id)</p>
<p>TABLE attack_groups(group_id PK, name, sectors, motivations)</p>
<p>TABLE baseline_controls(</p>
<p>control_id PK, framework, -- discriminant</p>
<p>description, -- texte réel du référentiel</p>
<p>category,</p>
<p>covers_risk_category, -- JSON list ; VIDE si non pertinent pour
l'atelier 4</p>
<p>framework_version</p>
<p>)</p></td>
</tr>
</tbody>
</table>

12.2 Référentiels par défaut — ISO 27001, ANSSI, RGPD, NIST

Quatre référentiels sont pré-suggérés dans le formulaire d'intake,
éditables par l'auditeur (déclaration, jamais inférence silencieuse,
section 12.4). Aucun autre référentiel n'est chargé par défaut (HIPAA,
PCI-DSS, etc. s'ajoutent à la demande, section 12.5).

| **Référentiel** | **Nature juridique** | **Contenu en base** | **Comportement atelier 4** |
|----|----|----|----|
| ISO 27001 (Annexe A) | Norme sous licence commerciale ISO | Texte réel, extrait depuis la copie sous licence détenue par l'entreprise — usage strictement interne, jamais redistribué à un client externe | Normal — toutes les entrées alimentent baseline_gaps_considered |
| ANSSI (guide d'hygiène informatique) | Publication libre de l'ANSSI | Texte réel, librement réutilisable | Normal |
| RGPD (Règlement UE 2016/679) | Règlement européen, publication publique | Texte réel des articles pertinents, librement réutilisable | Scindé — voir 12.3 |
| NIST (Cybersecurity Framework / SP 800-53) | Publication du gouvernement américain, domaine public | Texte réel, librement réutilisable | Normal — cadre intrinsèquement technique, aucune scission nécessaire |

12.3 Références à double nature — sécurité et impact légal, généralisé à
tout référentiel déclaré

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Décision importante — généralisée, non spécifique au
RGPD</strong></p>
<p>Certains référentiels déclarés par l'auditeur ne sont pas uniquement
des cadres de contrôles de sécurité — ce sont des textes juridiques. Le
RGPD en est l'exemple type (article 32 : sécurité du traitement,
comparable à un contrôle ISO 27001 ; article 83 : sanctions financières,
sans rapport avec la probabilité de réussite technique d'une attaque),
mais le mécanisme n'est jamais codé spécifiquement pour le RGPD — il
s'applique à tout référentiel déclaré par l'auditeur possédant des
dispositions de cette nature (ex. HIPAA possède ses propres obligations
de notification de violation et sanctions civiles sous HITECH, suivant
exactement le même schéma).</p></td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>TABLE baseline_controls (colonnes ajoutées)</p>
<p>...</p>
<p>covers_risk_category, -- JSON list ; vide si non pertinent pour
l'atelier 4</p>
<p>legal_impact_type, -- NULL | 'financial_penalty' |
'mandatory_notification' | 'liability'</p>
<p>legal_impact_details, -- texte réel décrivant la conséquence (plafond
de sanction,</p>
<p>-- délai de notification, etc.)</p></td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p># Entrée sécurité — comportement normal, alimente l'atelier 4</p>
<p>{ control_id: 'RGPD-Art32', framework: 'RGPD',</p>
<p>covers_risk_category: ['credential_access','exfiltration'],
legal_impact_type: null }</p>
<p># Entrée impact légal — exclue du filtre atelier 4, alimente
l'atelier 1 (section 15.1)</p>
<p>{ control_id: 'RGPD-Art83', framework: 'RGPD',</p>
<p>covers_risk_category: [],</p>
<p>legal_impact_type: 'financial_penalty',</p>
<p>legal_impact_details: 'Amende administrative jusqu'à 20M€ ou 4% du CA
mondial annuel, le montant le plus élevé étant retenu' }</p></td>
</tr>
</tbody>
</table>

get_legal_impact_provisions(applicable_frameworks) interroge cette même
table, filtrée sur legal_impact_type non nul, à travers tous les
référentiels déclarés par l'auditeur — jamais limité à un référentiel
nommément codé en dur. Ajouter un nouveau référentiel à double nature
(une autre loi nationale, un règlement sectoriel) suit exactement ce
même schéma, sans changement de code.

12.4 Déclaration des référentiels — jamais inférée

Les référentiels applicables sont déclarés explicitement par l'auditeur
(org_context_form.applicable_frameworks). Les quatre référentiels par
défaut apparaissent comme suggestion pré-remplie éditable ; l'auditeur
confirme, retire, ou ajoute (ex. HIPAA).

12.5 Ajout d'un nouveau référentiel

Insertion de nouvelles lignes dans baseline_controls avec un nouveau
framework — aucune nouvelle table, aucune nouvelle base, aucun
changement de schéma. Le même principe de scission sécurité/conformité
(section 12.3) s'applique à tout futur référentiel mixte, pas seulement
au RGPD — chaque entrée doit recevoir un covers_risk_category vide si
elle n'est pas pertinente pour le raisonnement d'attaque de l'atelier 4.

12.6 Schéma — base de mission

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>TABLE missions(mission_id PK, status, attck_version_used,</p>
<p>compliance_frameworks_declared, compliance_frameworks_versions,
restart_from)</p>
<p>TABLE workshop_versions(id PK, mission_id, workshop_number,
version_number,</p>
<p>output, status, created_at)</p>
<p>TABLE decision_log(id PK, mission_id, stage, timestamp,
decided_by,</p>
<p>action_taken, justification_given, estimated_cost_usd,
actual_cost_usd)</p>
<p>TABLE cost_calibration_log(id PK, input_tokens, output_tokens,
tool_calls,</p>
<p>wall_clock_seconds, model_used, logged_at)</p></td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Plafond de retours en arrière</strong></p>
<p>Se calcule directement en comptant les lignes de workshop_versions
pour un mission_id/workshop_number donnés — aucune colonne de comptage
séparée nécessaire. Plafond à 3 avant confirmation renforcée.</p></td>
</tr>
</tbody>
</table>

13\. Déploiement Docker

13.1 Principes

- Jamais de tag \`latest\` — image de base ou dépendances.

- Image de base : \`python:3.13.5-slim-trixie\` — jamais
  \`python:3-slim\` ni \`python:latest\`.

- Build multi-étapes : construction puis étape finale minimale.

- Utilisateur non-root créé explicitement, jamais root dans le conteneur
  final.

- \`--no-cache-dir\`, versions exactes dans requirements.txt (ex.
  \`agno==2.6.12\`).

- .dockerignore excluant fichiers de développement, bases locales de
  test, secrets.

- Volumes distincts : référence (lecture seule après chargement) et
  mission (lecture-écriture).

- Clés API jamais dans l'image — variables d'environnement au lancement
  uniquement.

13.2 Dockerfile (niveau conception)

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>FROM python:3.13.5-slim-trixie AS builder</p>
<p>installer dépendances de compilation, créer venv, installer
requirements.txt (épinglé)</p>
<p>FROM python:3.13.5-slim-trixie AS final</p>
<p>créer utilisateur non-root</p>
<p>copier uniquement le venv depuis builder</p>
<p>copier le code applicatif</p>
<p>utilisateur non-root comme utilisateur d'exécution</p>
<p>HEALTHCHECK</p>
<p>CMD lance l'orchestrateur (AgentOS / point d'entrée CLI)</p></td>
</tr>
</tbody>
</table>

13.3 docker-compose — services

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>services:</p>
<p>reference-db-loader: # exécuté une fois, charge ATT&amp;CK +
référentiels, puis s'arrête</p>
<p>volumes: [reference_db_data:/data/reference]</p>
<p>app:</p>
<p>depends_on: [reference-db-loader]</p>
<p>volumes:</p>
<p>- reference_db_data:/data/reference:ro</p>
<p>- mission_db_data:/data/mission</p>
<p>environment: [MODEL_ID, OPENROUTER_API_KEY] # injectées, jamais dans
l'image ; OpenRouter est l'unique fournisseur, seul MODEL_ID distingue
test et production (section 3.2)</p>
<p>volumes: { reference_db_data:, mission_db_data: }</p></td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Concurrence SQLite</strong></p>
<p>Écritures continues mais depuis un seul processus orchestrateur à la
fois — proportionné à l'usage actuel (CLI, une mission active par
instance). À réévaluer seulement si le projet évolue vers plusieurs
missions strictement simultanées.</p></td>
</tr>
</tbody>
</table>

14\. Modèles de données typés — liste de référence

Aucune donnée ne circule sous forme de dictionnaire libre entre les
couches.

| **Type** | **Rôle** |
|----|----|
| Fact | Toute affirmation sur l'organisation, avec provenance complète (section 5) |
| MissionContext | Objet unique consolidant tous les Facts validés avant l'atelier 1 |
| EssentialAsset / SupportAsset | Biens essentiels / biens supports (atelier 1) |
| FearedEvent | Événement redouté, avec gravité (atelier 1) |
| RiskSource | Source de risque (atelier 2) |
| StrategicScenario | Scénario stratégique (atelier 3) |
| OperationalScenario | Scénario opérationnel (atelier 4) |

15\. Atelier 1 — Cadrage et socle de sécurité

Agent unique. Consomme le Mission Context (jamais les documents bruts).
Extrait biens essentiels/supports, événements redoutés avec gravité, et
évalue le socle de sécurité contre les référentiels déclarés.

Schéma d'entrée

|  |
|----|
| w1_input = MissionContext \# Facts validés uniquement, jamais un document brut |

Schéma de sortie

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>w1_output = {</p>
<p>biens_essentiels: [EssentialAsset], biens_supports:
[SupportAsset],</p>
<p>evenements_redoutes: [{ id, description, categorie_impact, gravite
}],</p>
<p>baseline_scope_decisions: [...], # jamais vide</p>
<p>baseline_gaps_full: [...], # avec framework/control_id, gap_id
haché</p>
<p>}</p></td>
</tr>
</tbody>
</table>

Fonctionnement interne

6.  Pour chaque framework déclaré (section 12.4) :
    get_baseline_controls(framework), puis assess_control(control,
    context) — évaluation par la preuve (evidence citée, verdict,
    confidence), jamais un verdict direct.

7.  Verdict 'insufficient_information' → question de suivi à l'auditeur
    ; sans réponse, reste 'unverified', jamais reclassé silencieusement.

8.  Filtrer les entrées RGPD à covers_risk_category vide (section 12.3)
    — suivies dans baseline_gaps_full mais jamais proposées au filtre de
    pertinence de l'atelier 4.

9.  Détection de doublons inter-référentiels : groupement par
    covers_risk_category, suggestion LLM des fusions possibles,
    validation humaine obligatoire par paire (jamais de fusion
    automatique).

10. gap_id dérivé par hachage du contenu (stable across reruns), jamais
    par compteur séquentiel.

11. Vérifier baseline_scope_decisions : toute catégorie non-cyber
    couverte ou explicitement exclue avec justification.

12. Évaluation d'impact légal (assess_legal_impact, section 15.1) :
    indépendante du socle de sécurité, contribue à la gravité même en
    l'absence de tout écart de contrôle constaté.

Technologie

- Agent Agno unique, Toolkit dédié (get_baseline_controls,
  assess_control, get_legal_impact_provisions, assess_legal_impact,
  get_gap_consequences).

- Validation humaine via HITL natif Agno.

Interactions

- Consomme : MissionContext.

- Produit vers : Atelier 2 (contexte), Atelier 4 (baseline_gaps stripé,
  section 15 note), Reporting (baseline_gaps_full complet).

Fiche de test

Entrée de test :

|  |
|----|
| { 'mission_context': { facts: \[...\], 'applicable_frameworks': \['ISO27001','ANSSI_hygiene','RGPD','NIST'\] } } |

Sortie exacte attendue (sous-composant déterministe) :

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>assert w1_output['baseline_scope_decisions'] is not empty</p>
<p>assert every RGPD-Art30-type entry has covers_risk_category == []</p>
<p>assert every RGPD-Art32-type entry has covers_risk_category !=
[]</p></td>
</tr>
</tbody>
</table>

Critères de validation (sous-composant génératif) :

- Le contrôle ISO27001-A.9.4 doit citer explicitement le passage source
  pertinent (evidence vérifiable dans le Mission Context).

- Chaque gravité doit être une des 4 valeurs fixes (Minimale,
  Significative, Grave, Critique).

15.1 Évaluation d'impact légal — mécanisme dédié dans l'atelier 1

Ce mécanisme est distinct de l'évaluation du socle de sécurité (section
15, principale). Il répond à une question différente : quelle est la
gravité d'un événement redouté du seul fait de la loi, indépendamment de
la présence ou non d'un écart de contrôle de sécurité.

categorie_impact — enum fixe, aligné sur la pratique professionnelle
réelle

Aligné sur la structure d'un rapport EBIOS RM professionnel réel
consulté durant ce projet (colonnes Financiers / Sur le fonctionnement /
Sur l'image / Juridiques / Sur la vie privée des personnes concernées).

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>categorie_impact ∈ {</p>
<p>'financier', 'fonctionnement', 'image',</p>
<p>'juridique', # sanctions, mise en demeure, contentieux</p>
<p>'vie_privee_personnes_concernees', # impact sur les personnes dont
les données sont traitées</p>
<p>}</p></td>
</tr>
</tbody>
</table>

Fonctionnement

13. Pour chaque événement redouté impliquant des données personnelles ou
    une obligation légale spécifique : appeler
    get_legal_impact_provisions(applicable_frameworks) — interroge tous
    les référentiels déclarés par l'auditeur, pas seulement le RGPD
    (section 12.3).

14. assess_legal_impact cite le fait précis du Mission Context
    justifiant la pertinence de la disposition légale, ET la disposition
    légale elle-même (ex. plafond de sanction, délai de notification) —
    même discipline d'évaluation par la preuve que assess_control,
    jamais un verdict de gravité affirmé sans citation double.

15. Contribution à la gravité de l'événement redouté : indépendante de
    baseline_gaps — un événement peut recevoir une gravité juridique
    élevée même si aucun écart de sécurité n'a été détecté, puisque la
    conséquence légale découle du texte de loi, pas d'un contrôle
    manquant.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>def assess_legal_impact(evenement_redoute, mission_context,
applicable_frameworks):</p>
<p>provisions = get_legal_impact_provisions(applicable_frameworks)</p>
<p>relevant = [p for p in provisions if concerns(p, evenement_redoute,
mission_context)]</p>
<p>return [{</p>
<p>'categorie_impact': 'juridique',</p>
<p>'provision_citee': p.legal_impact_details,</p>
<p>'evidence_mission_context': '&lt;fait précis cité du Mission
Context&gt;',</p>
<p>} for p in relevant]</p></td>
</tr>
</tbody>
</table>

Ce mécanisme s'applique à tout référentiel légal déclaré par l'auditeur,
jamais uniquement au RGPD — si l'auditeur déclare HIPAA pour un client
de santé américain, les mêmes fonctions s'appliquent aux dispositions de
notification et de sanction propres à HIPAA, sans aucune modification de
code.

16\. Atelier 2 — Sources de risque

Agent unique. Identifie et priorise les couples SR/OV en s'appuyant sur
les groupes ATT&CK réels.

Schéma d'entrée

|  |
|----|
| w2_input: Workshop2Input = { biens_essentiels, evenements_redoutes } \# contrat étroit, section 9 |

Schéma de sortie

|  |
|----|
| w2_output = { couples_sr_ov: \[{ sr_id, description, ov_id, objectif, ressources, motivation, pertinence, vraisemblance_initiale }\] } |

Fonctionnement interne

16. Appeler get_groups_by_sector / get_groups_by_motivation pour ancrer
    les sources sur des groupes ATT&CK réels.

17. Vraisemblance initiale : répond uniquement à 'cette source
    cible-t-elle cette organisation', pas à la réussite technique
    (nuance méthodologique, atelier 4).

Technologie

- Agent Agno unique, Toolkit ATT&CK (lecture seule).

Interactions

- Consomme : Workshop2Input dérivé de l'atelier 1 (pas la sortie
  complète).

- Produit vers : Atelier 3.

Fiche de test

Entrée de test :

|                                                                 |
|-----------------------------------------------------------------|
| { 'biens_essentiels': \[...\], 'evenements_redoutes': \[...\] } |

Sortie exacte attendue (sous-composant déterministe) :

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>assert every entry.pertinence in ['Faible','Moyen','Élevé']</p>
<p>assert every entry.vraisemblance_initiale in
['V1','V2','V3','V4']</p></td>
</tr>
</tbody>
</table>

Critères de validation (sous-composant génératif) :

- La pertinence réelle attribuée à chaque couple (non testable en sortie
  exacte).

17\. Atelier 3 — Scénarios stratégiques et point de validation de
comptage

Agent unique avec boucle interne propose → critique. Contient l'unique
point de validation portant sur le nombre de scénarios (N) — l'atelier 4
n'a plus de point de passage propre pour ce comptage.

Schéma d'entrée

|                                              |
|----------------------------------------------|
| w3_input: Workshop3Input = { couples_sr_ov } |

Schéma de sortie

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>w3_output = { scenarios_strategiques: [{ id, sr_id, ov_id,
resume, parties_prenantes, vraisemblance_pertinence }],</p>
<p>gate_decision: { n, action, justification } }</p></td>
</tr>
</tbody>
</table>

Fonctionnement interne

18. Passe 1 (propose) : générer les scénarios. Passe 2 (critique) : même
    agent, élague les quasi-doublons.

19. N = nombre de scénarios. estimate_cost_and_time(N).

20. N≤6 → \[Oui\]\[Annuler\]. 6\<N≤12 → \[Lancer tout de
    même\]\[Fusionner\]\[Choisir sous-ensemble\]\[Annuler\]. N\>12 →
    \[Fusionner\]\[Choisir sous-ensemble\]\[Annuler\] (jamais de 'lancer
    tout de même' au-delà du seuil dur).

21. Fusionner/Choisir un sous-ensemble ré-évalue N contre les mêmes
    seuils (récursion), motif non vide obligatoire.

Technologie

- Agent Agno unique ; Router/Condition Agno pour le branchement sur N ;
  ask_human via HITL natif.

Interactions

- Consomme : sortie de l'atelier 2.

- Produit vers : Atelier 4 (liste finale approuvée, aucune re-validation
  en aval).

Fiche de test

Entrée : { 'couples_sr_ov': \[ /\* 9 couples \*/ \] }

Sortie exacte attendue (logique de seuil, déterministe) :

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>estimate_cost_and_time(9) → 6&lt;N≤12 → options ==
['run_anyway','merge','choose_subset','cancel']</p>
<p>estimate_cost_and_time(14) → N&gt;12 → options ==
['merge','choose_subset','cancel']</p>
<p>assert 'run_anyway' not in options_for_14</p></td>
</tr>
</tbody>
</table>

Critère de validation (génératif) : le contenu réel des scénarios
produits.

18\. Atelier 4 — Scénarios opérationnels (fan-out / fan-in)

Seul atelier avec structure multi-agents. N instances Agno Agent
indépendantes (jamais Team), une par scénario stratégique, dispatchées
via asyncio.gather.

Schéma d'entrée (par sous-agent)

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>subagent_input = {</p>
<p>scenario: {...}, mission_context_relevant_facts: [...],</p>
<p>baseline_gaps_for_w4: [ { gap_id, weakness, risk_categories } ]</p>
<p># STRIPÉ des références framework/control_id — l'atelier 4 ne
connaît</p>
<p># jamais l'origine réglementaire, seulement le fait brut (section
12.3, 15)</p>
<p>}</p></td>
</tr>
</tbody>
</table>

Schéma de sortie (par sous-agent)

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>subagent_output = {</p>
<p>scenario_id, attack_path: [{ tactic, technique_id, technique_name,
justification }],</p>
<p># technique_id peut être null — jamais d'invention d'ID</p>
<p>revised_likelihood, revised_risk_level,
likelihood_revision_reason,</p>
<p>baseline_gaps_considered: [ { gap_id, impact_type, impact_on_scenario
} ],</p>
<p># impact_on_scenario NON VIDE quel que soit impact_type, sans
exception</p>
<p>new_baseline_gap_identified: {...} | null,</p>
<p>}</p></td>
</tr>
</tbody>
</table>

Fonctionnement interne

22. Fan-out : un appel par scénario, N = len(scenarios_strategiques),
    même prompt-template et même Toolkit pour tous.

23. Après chaque retour : extraction des IDs cités, comparaison avec les
    IDs réellement retournés par les outils (contrôle par code, jamais
    par LLM).

24. Contrôle baseline_gaps_considered : tout gap pertinent présent ;
    tout impact_on_scenario non vide, y compris no_impact/not_relevant.

25. Revue humaine en lot : tous les N résultats ensemble, anomalies en
    évidence. Actions : Confirmer / Réviser (motif obligatoire,
    exclusion explicite de la réponse rejetée dans le prompt de reprise)
    / Rejeter et refaire.

26. Aperçu de coût (estimate_cost_and_time(1)) avant tout second passage
    sur un scénario rejeté.

27. Boucle tant que des reprises sont en attente — la cohérence n'est
    PAS vérifiée tant qu'un scénario est en attente. Plafond 3
    itérations.

28. Une fois stable : vérification de cohérence (un seul appel LLM) —
    techniques contradictoires, doublons, révision de niveau de risque.
    Rejet à ce stade rouvre la boucle.

29. Fusion finale, finalisation du niveau de risque.

Technologie

- N instances Agno Agent via asyncio.gather ; Loop Agno pour la reprise
  (max_iterations=3).

Interactions

- Consomme : liste approuvée de l'atelier 3, baseline_gaps_for_w4 stripé
  de l'atelier 1.

- Produit vers : Atelier 5.

Fiche de test

Entrée : { 'scenarios_strategiques': \[/\* 3 \*/\],
'baseline_gaps_for_w4': \[{ 'gap_id':'BG-a1b2c3d4', 'weakness':'Pas de
MFA sur VPN', 'risk_categories':\['initial_access'\] }\] }

Sortie exacte attendue (déterministe) :

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>cited_ids=['T1566.001','T9999.999'];
tool_returned=['T1566.001']</p>
<p>assert mismatches == ['T9999.999'] and scenario_flagged == True</p>
<p>entry={'impact_type':'no_impact','impact_on_scenario':''}</p>
<p>assert flagged_as_weak_entry == True # vide même en
no_impact</p></td>
</tr>
</tbody>
</table>

Critères de validation (génératif) :

- Chaque attack_path couvre les tactiques attendues, technique_id réel
  ou null+step_description.

- revised_likelihood ∈ {V1,V2,V3,V4} uniquement.

- BG-a1b2c3d4 doit apparaître avec impact_type ≠ not_relevant sans
  justification solide du contraire.

19\. Atelier 5 — Traitement du risque

Agent unique consommant la sortie finalisée de l'atelier 4.

Schéma d'entrée

|                                                                     |
|---------------------------------------------------------------------|
| w5_input: Workshop5Input = { scenarios_finalises_avec_attack_path } |

Schéma de sortie

|  |
|----|
| w5_output = { mesures: \[{ id, description, scenarios_associes, mitigation_ids_attck, cout, efficacite, delai, priorite }\] } |

Fonctionnement interne

30. get_mitigations_for_technique(id) pour chaque technique citée en
    atelier 4.

31. Matrice de priorisation multicritère.

32. Inclusion des mesures de réduction des écarts du socle (y compris
    RGPD Article 32, jamais les entrées RGPD à covers_risk_category vide
    qui restent hors scope technique).

Technologie

- Agent Agno unique, Toolkit ATT&CK.

Interactions

- Consomme : sortie finalisée de l'atelier 4.

- Produit vers : Agent de reporting.

Fiche de test

Entrée de test :

|                                                     |
|-----------------------------------------------------|
| { 'scenarios_finalises_avec_attack_path': \[...\] } |

Sortie exacte attendue (sous-composant déterministe) :

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>assert every mitigation_ids_attck are real IDs from
get_mitigations_for_technique</p>
<p>assert every priorite in ['Faible','Moyenne','Élevée']</p></td>
</tr>
</tbody>
</table>

Critères de validation (sous-composant génératif) :

- Le contenu réel des mesures recommandées.

20\. Agent de reporting

20.1 Deux documents, deux stratégies

| **Document** | **Génération** | **Testabilité** |
|----|----|----|
| Rapport de mission (entreprise) | LLM — narratif, version courante uniquement | Critères de validation seulement |
| Annexe d'audit (auditeur) | Rendu de données pur (python-docx), aucun LLM | Sortie exacte intégralement testable |

20.2 Interaction avec l'auditeur

33. Document pré-rempli généré une fois (templating, pas de LLM).

34. Auditeur remplit les champs vides dans Word.

35. Code détecte les champs non vides (pas de LLM).

36. Appel LLM uniquement pour les champs remplis, sous-ensemble
    pertinent de mission_state seulement.

37. Validation anti-hallucination : toute affirmation cite un champ
    précis de mission_state, contrôle automatique avant ajout.

20.3 Provenance des écarts — séparée par document

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p><strong>Rappel</strong></p>
<p>L'atelier 4 ne reçoit jamais l'identité du référentiel — seulement
weakness et risk_categories. Le lien complet (control_id, framework, y
compris la distinction sécurité/légal du RGPD) reste dans
baseline_gaps_full et n'est restitué que dans l'annexe d'audit.</p></td>
</tr>
</tbody>
</table>

Fiche de test — Annexe d'audit (déterministe complet)

Entrée : { mission_state avec w3_versions (v1 superseded, v2 approved),
decision_log, attck_version_used:'v15.1',
compliance_frameworks_versions:{'ISO27001':'2022','ANSSI_hygiene':'2024','RGPD':'2016/679','NIST':'CSF
2.0'} }

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>assert audit_doc row for w3_versions[0] labeled 'superseded'</p>
<p>assert audit_doc row for w3_versions[1] labeled 'approved'</p>
<p>assert audit_doc.rgpd_version_field == '2016/679'</p>
<p>assert audit_doc.nist_version_field == 'CSF 2.0'</p>
<p>assert every abnormal_event has blank 'Appréciation de l'auditeur'
field</p></td>
</tr>
</tbody>
</table>

Fiche de test — Rapport de mission : critère de validation uniquement
(version courante seule, scénarios approuvés seuls, niveaux en
contexte).

21\. Limites résiduelles — état consolidé et final

| **Limite** | **Statut** |
|----|----|
| Sélection des référentiels de conformité | Résolu — déclaration explicite par l'auditeur, quatre suggestions par défaut (section 12.4) |
| Verdict 'insufficient_information' sans comportement défini | Résolu — état 'unverified' permanent, suivi à l'auditeur |
| Absence d'aperçu de coût avant reprise d'un scénario W4 | Résolu — estimate_cost_and_time(1) avant chaque reprise |
| Cohérence non re-exécutée après reprise partielle | Résolu — évaluée uniquement une fois l'ensemble stable |
| Absence de plafond sur les retours en arrière | Résolu — dérivé du comptage workshop_versions, plafond 3 |
| Doublons de gaps entre référentiels | Résolu — groupement + suggestion LLM + validation humaine par paire |
| Absence de citation source pour les extractions documentaires | Résolu — source_quote obligatoire et non vide |
| Risque d'omission silencieuse (niveau Optionnel) | Résolu — matrice à deux niveaux, aucune omission sans justification pour tout champ suivi comme Fact |
| Sur-application du modèle Fact | Résolu — portée limitée aux affirmations sur l'organisation |
| RGPD traité comme un cadre de sécurité pur | Résolu — scission sécurité/impact légal généralisée à tout référentiel déclaré via legal_impact_type (section 12.3) |
| Impact légal absent de la gravité de l'atelier 1 (existait uniquement côté atelier 4 via le socle) | Résolu — assess_legal_impact dédié, indépendant du socle de sécurité, categorie_impact pinné à 5 valeurs alignées sur la pratique professionnelle réelle (section 15.1) |
| Tension température minimale / révision significative | Traité par exclusion explicite de la réponse précédente dans le prompt de reprise — non définitivement validé empiriquement, s'applique à tout Fact d'origine assessment |
| Qualité des motifs de justification obligatoires | Explicitement hors périmètre technique — responsabilité de gouvernance humaine |
| Traitement des données sensibles du client (chiffrement au repos, rétention) | Différé à la fin du projet, comme demandé |
| Charge de travail liée à l'adoption du modèle Fact et des quatre référentiels | Non réconciliée avec la répartition de charge déjà établie entre les quatre personnes — à traiter avant démarrage du développement |
