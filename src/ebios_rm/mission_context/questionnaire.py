"""The complete, professional EBIOS RM intake questionnaire — catalog form.

This is the single source of truth for the client-facing intake document AND for
ingestion (conception §11.1, extended). It is a *catalog* of questions grouped in
sections, not a rigid schema: the Word document (questionnaire.py -> pandoc) and
the ingestion mapping both read from it, so they can never drift apart.

Design rules:
- Each question has an ``id`` that becomes the Fact ``field_name`` when the answer
  is ingested (origin 'declaration' if the client filled it, 'extraction' if the
  agent pulled it from an attached document — source_quote mandatory, §5.3).
- Each question carries a plain-language ``explanation`` written for a
  NON-TECHNICAL reader, because the document is handed to business/management
  contacts, not only to IT. No jargon is left unexplained.
- ``priority`` follows the two-level matrix (§7): CRITICAL blocks the study until
  answered/confirmed; IMPORTANT is asked and may be skipped only with a non-empty
  justification (§8). There is no silently-optional level.
- The catalog is intentionally long and exhaustive — completeness matters more
  than brevity for a real audit intake.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ebios_rm.domain.enums import PriorityLevel

C = PriorityLevel.CRITICAL
I = PriorityLevel.IMPORTANT


@dataclass(frozen=True)
class Question:
    """One intake question. ``id`` becomes the Fact field_name on ingestion."""

    id: str
    question: str
    explanation: str  # plain language, for a non-technical reader
    priority: PriorityLevel
    answer_hint: str = ""   # expected form of the answer
    example: str = ""       # a concrete example answer
    # False for questions the follow-up logic must never re-ask (genuinely optional,
    # e.g. the list of attached documents).
    askable: bool = True
    # Only ask this question when the referenced question was answered affirmatively
    # (e.g. data-subject categories only matter if personal data is processed).
    depends_on_true: str | None = None


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    intro: str
    questions: tuple[Question, ...] = field(default_factory=tuple)


QUESTIONNAIRE: tuple[Section, ...] = (
    Section(
        "identite", "1. Identité et gouvernance de l'organisation",
        "Cette première partie décrit qui vous êtes et comment la sécurité est "
        "organisée chez vous. Elle sert à cadrer toute l'étude.",
        (
            Question(
                "organisation_nom", "Quel est le nom de l'organisation auditée ?",
                "Le nom officiel de l'entité concernée par l'audit (société, établissement, direction).",
                C, "Texte", "Clinique du Val Fleuri",
            ),
            Question(
                "forme_juridique", "Quelle est sa forme juridique et son statut ?",
                "S'agit-il d'une entreprise privée, d'une association, d'un établissement public, "
                "d'une filiale d'un groupe ? Cela influence les obligations réglementaires.",
                I, "Texte", "SAS privée, filiale d'un groupe de santé",
            ),
            Question(
                "secteur_activite", "Quel est le secteur d'activité principal ?",
                "Le domaine dans lequel vous opérez (santé, finance, industrie, service public…). "
                "Le secteur détermine les menaces typiques et les référentiels applicables.",
                C, "Texte", "Santé — établissement de soins privé",
            ),
            Question(
                "activites_description", "Décrivez en quelques phrases votre activité et vos missions.",
                "Expliquez simplement ce que fait l'organisation au quotidien et pour qui. "
                "Aucune connaissance technique n'est requise ici.",
                C, "Texte libre",
                "Prise en charge médicale de patients en hospitalisation et consultations externes.",
            ),
            Question(
                "taille_effectif", "Quel est l'effectif total (nombre de personnes) ?",
                "Le nombre approximatif de personnes travaillant dans l'organisation (salariés, "
                "intérimaires, prestataires permanents). Cela donne une idée de la taille du système.",
                I, "Nombre", "420",
            ),
            Question(
                "perimetre_geographique", "Sur quels pays / sites l'audit porte-t-il ?",
                "Listez les lieux (villes, pays, sites) concernés par l'étude. Un site à l'étranger "
                "peut impliquer d'autres lois.",
                I, "Liste", "France (siège de Lyon, site de Grenoble)",
            ),
            Question(
                "gouvernance_securite", "Qui est responsable de la sécurité de l'information ?",
                "Existe-t-il un RSSI (Responsable de la Sécurité des Systèmes d'Information), un DSI, "
                "un DPO (délégué à la protection des données) ? Un RSSI pilote la cybersécurité ; un DPO "
                "veille au respect de la loi sur les données personnelles.",
                I, "Texte", "Un RSSI à temps partiel et un DPO externe mutualisé",
            ),
            Question(
                "maturite_securite", "Comment évalueriez-vous votre maturité en cybersécurité ?",
                "Votre ressenti global : débutante, en cours de structuration, mature. Il n'y a pas de "
                "mauvaise réponse — cela nous aide à calibrer nos attentes.",
                I, "Choix / texte", "En cours de structuration",
            ),
        ),
    ),
    Section(
        "perimetre", "2. Périmètre et objectifs de l'audit",
        "Ici nous délimitons précisément ce qui est étudié et pourquoi.",
        (
            Question(
                "objectifs_etude", "Quels sont vos objectifs pour cet audit ?",
                "Ce que vous attendez concrètement : obtenir une certification, répondre à une exigence "
                "d'un client, réduire un risque connu, préparer une mise en conformité…",
                C, "Texte libre", "Se mettre en conformité et réduire le risque de fuite de données patients",
            ),
            Question(
                "perimetre_inclus", "Quels systèmes / services sont DANS le périmètre ?",
                "La liste de ce qui doit être analysé (applications, sites, activités). Tout ce qui n'est "
                "pas listé sera considéré hors périmètre.",
                C, "Liste", "SIH, imagerie, messagerie, accès distant des médecins",
            ),
            Question(
                "perimetre_exclu", "Quels systèmes / services sont explicitement HORS périmètre ?",
                "Ce que vous souhaitez volontairement exclure de l'étude, et si possible pourquoi. "
                "Une exclusion doit être un choix conscient, jamais un oubli.",
                I, "Liste + justification", "La billetterie de la cafétéria (sans donnée sensible)",
            ),
            Question(
                "commanditaires", "Qui commandite l'audit et qui décidera in fine ?",
                "La ou les personnes qui portent le projet et qui approuveront les conclusions "
                "(direction, comité, sponsor). L'audit assiste la décision, mais la décision reste humaine.",
                I, "Texte", "La Direction Générale et le Directeur des Systèmes d'Information",
            ),
            Question(
                "contraintes_calendrier", "Existe-t-il des contraintes de calendrier ou d'échéance ?",
                "Une date butoir (audit client, renouvellement de certification, échéance réglementaire) "
                "qui structure le planning.",
                I, "Texte", "Certification HDS à renouveler en mars prochain",
            ),
        ),
    ),
    Section(
        "metier", "3. Contexte métier et valeurs essentielles",
        "Cette partie identifie ce qui est vital pour votre organisation — le cœur de l'analyse EBIOS RM. "
        "Répondez du point de vue métier, pas informatique.",
        (
            Question(
                "processus_metier_critiques", "Quels sont vos processus métier critiques ?",
                "Les activités sans lesquelles l'organisation ne peut pas fonctionner. Pensez : « si cela "
                "s'arrête, nous sommes bloqués ». Ce sont les futurs 'biens essentiels' de l'étude.",
                C, "Liste", "Prise en charge des patients, gestion du dossier médical, imagerie",
            ),
            Question(
                "informations_sensibles", "Quelles informations sont les plus sensibles / précieuses ?",
                "Les données dont la fuite, la perte ou l'altération serait grave (données clients, "
                "secrets de fabrication, données de santé, données financières).",
                C, "Liste", "Dossiers médicaux, résultats d'examens, données RH",
            ),
            Question(
                "impact_arret", "Que se passerait-il si votre activité s'arrêtait une journée ?",
                "Décrivez les conséquences concrètes d'une interruption (sécurité des personnes, pertes "
                "financières, atteinte à l'image, conséquences légales). Cela nourrit la gravité des "
                "événements redoutés.",
                C, "Texte libre", "Report de soins, risque pour les patients, perte de revenus, atteinte à la réputation",
            ),
            Question(
                "obligations_metier", "Avez-vous des obligations de service ou contractuelles fortes ?",
                "Des engagements envers vos clients ou l'État (continuité de service, délais, disponibilité "
                "garantie) que la sécurité doit préserver.",
                I, "Texte", "Continuité des soins 24/7, engagements de disponibilité envers l'ARS",
            ),
        ),
    ),
    Section(
        "cartographie", "4. Cartographie du système d'information",
        "Une vue d'ensemble de votre informatique. Restez simple : nous approfondirons si besoin.",
        (
            Question(
                "systeme_information_resume", "Décrivez globalement votre système d'information.",
                "Un résumé libre : vos principales applications, où elles tournent, comment les gens "
                "travaillent. Comme si vous l'expliquiez à un nouveau collègue.",
                C, "Texte libre", "SIH central, messagerie Microsoft 365, imagerie PACS, postes Windows",
            ),
            Question(
                "applications_principales", "Quelles sont vos principales applications métier ?",
                "Les logiciels essentiels à votre activité, avec leur rôle (par ex. logiciel de gestion, "
                "outil de production, ERP). Précisez s'ils sont internes ou fournis par un éditeur.",
                I, "Liste", "SIH (éditeur X), PACS imagerie (éditeur Y), paie (SaaS)",
            ),
            Question(
                "parc_informatique", "Combien de serveurs et de postes de travail environ ?",
                "Un ordre de grandeur suffit. Cela indique la surface à protéger.",
                I, "Nombres", "~30 serveurs, ~350 postes",
            ),
            Question(
                "systemes_exploitation", "Quels systèmes d'exploitation utilisez-vous ?",
                "Les systèmes de vos postes et serveurs (Windows, Linux, macOS) et leurs versions si "
                "vous les connaissez. Des versions anciennes peuvent être vulnérables.",
                I, "Liste", "Windows 11 sur les postes, Windows Server 2019, quelques Linux",
            ),
            Question(
                "systemes_obsoletes", "Utilisez-vous encore des systèmes anciens / non maintenus ?",
                "Des logiciels ou machines qui ne reçoivent plus de mises à jour de sécurité (ex. "
                "Windows 7, vieux équipements médicaux). Ils sont souvent les points faibles.",
                I, "Texte", "Deux échographes sous un ancien Windows non mis à jour",
            ),
        ),
    ),
    Section(
        "hebergement", "5. Hébergement et cloud",
        "Où vivent vos données et vos applications.",
        (
            Question(
                "hebergement", "Comment est hébergé votre système d'information ?",
                "« Sur site » = dans vos locaux ; « cloud » = chez un fournisseur sur Internet ; "
                "« hybride » = un mélange des deux.",
                C, "sur_site | cloud | hybride", "hybride",
            ),
            Question(
                "fournisseurs_cloud", "Quels fournisseurs cloud et services en ligne utilisez-vous ?",
                "Les grands services externes (Microsoft 365, Google, AWS, Azure) et applications en "
                "ligne (SaaS) que vous utilisez. Vos données y transitent ou y résident.",
                I, "Liste", "Microsoft 365, hébergeur HDS pour le SIH",
            ),
            Question(
                "localisation_donnees", "Où sont physiquement stockées vos données ?",
                "Le ou les pays d'hébergement. Un stockage hors Union Européenne peut poser des "
                "questions réglementaires (RGPD).",
                I, "Texte", "France (hébergeur certifié HDS)",
            ),
            Question(
                "certifications_hebergeur", "Vos hébergeurs ont-ils des certifications de sécurité ?",
                "Par exemple HDS (hébergeur de données de santé), ISO 27001, SecNumCloud. Ces labels "
                "attestent d'un niveau de sécurité de votre prestataire.",
                I, "Texte", "Hébergeur certifié HDS et ISO 27001",
            ),
        ),
    ),
    Section(
        "reseau", "6. Réseau et accès distant",
        "Comment vos systèmes communiquent entre eux et avec l'extérieur.",
        (
            Question(
                "architecture_reseau", "Comment votre réseau est-il organisé ?",
                "Décrivez simplement : un seul réseau à plat, ou des zones séparées (bureautique, "
                "serveurs, invités) ? La séparation limite la propagation d'une attaque.",
                I, "Texte", "Réseau segmenté : bureautique, serveurs, réseau médical isolé",
            ),
            Question(
                "exposition_internet", "Quels services sont accessibles depuis Internet ?",
                "Ce qui est visible de l'extérieur (site web, portail, messagerie, accès distant). "
                "Tout ce qui est exposé peut être attaqué.",
                I, "Liste", "Portail patient, webmail, VPN",
            ),
            Question(
                "teletravail_autorise", "Le télétravail est-il autorisé ?",
                "Vos collaborateurs se connectent-ils depuis l'extérieur (domicile, déplacement) ?",
                C, "Oui / Non", "Oui, pour les fonctions administratives et les médecins",
            ),
            Question(
                "acces_distant_moyens", "Par quels moyens accède-t-on à distance au système ?",
                "VPN = tunnel sécurisé ; MFA = double authentification (mot de passe + code) ; "
                "VDI = bureau virtuel. Ces moyens protègent les connexions à distance.",
                I, "Liste", "VPN avec MFA pour les administratifs, VPN simple pour les médecins",
            ),
            Question(
                "wifi", "Disposez-vous de réseaux Wi-Fi, et sont-ils séparés (invités / interne) ?",
                "Un Wi-Fi invité ouvert mais isolé du réseau interne évite qu'un visiteur atteigne vos "
                "systèmes sensibles.",
                I, "Texte", "Wi-Fi interne protégé + Wi-Fi invité isolé",
            ),
            Question(
                "interconnexions_tiers", "Avez-vous des connexions permanentes avec des partenaires ?",
                "Des liaisons directes avec des prestataires ou partenaires (télémaintenance, échanges "
                "de données). Elles étendent votre surface d'exposition.",
                I, "Liste", "Liaison de télémaintenance avec l'éditeur du SIH",
            ),
        ),
    ),
    Section(
        "identites", "7. Identités et gestion des accès",
        "Comment vous contrôlez qui accède à quoi.",
        (
            Question(
                "gestion_identites", "Comment gérez-vous les comptes utilisateurs ?",
                "Avez-vous un annuaire central (ex. Active Directory) ? Comment sont créés, modifiés et "
                "surtout supprimés les comptes quand une personne part ?",
                I, "Texte", "Active Directory ; création/suppression via un processus RH",
            ),
            Question(
                "authentification_forte", "L'authentification multifacteur (MFA) est-elle en place ?",
                "La MFA demande une seconde preuve en plus du mot de passe (code sur téléphone, appli, "
                "clé). Précisez où elle s'applique (messagerie, VPN, applications sensibles).",
                C, "Texte", "MFA sur la messagerie et le VPN administratif, pas encore sur le SIH",
            ),
            Question(
                "comptes_privilegies", "Comment sont gérés les comptes à privilèges (administrateurs) ?",
                "Les comptes « administrateur » ont tous les pouvoirs et sont la cible n°1 des attaquants. "
                "Sont-ils limités, nominatifs, surveillés ?",
                I, "Texte", "Comptes admin nominatifs, mais pas de coffre-fort de mots de passe",
            ),
            Question(
                "politique_mots_de_passe", "Quelle est votre politique de mots de passe ?",
                "Les règles imposées (longueur, complexité, renouvellement). Des mots de passe faibles "
                "sont facilement devinés.",
                I, "Texte", "12 caractères minimum, pas de renouvellement forcé",
            ),
        ),
    ),
    Section(
        "postes", "8. Postes de travail et serveurs",
        "La protection des ordinateurs et serveurs eux-mêmes.",
        (
            Question(
                "edr_av_deploye", "Quel antivirus / EDR est déployé ?",
                "Un antivirus détecte les logiciels malveillants ; un EDR (détection et réponse) est un "
                "antivirus avancé qui repère aussi les comportements suspects. Précisez le produit.",
                I, "Texte", "Microsoft Defender for Endpoint sur tous les postes",
            ),
            Question(
                "mises_a_jour", "Comment appliquez-vous les mises à jour de sécurité (correctifs) ?",
                "Les éditeurs publient régulièrement des correctifs qui bouchent des failles. Sont-ils "
                "appliqués automatiquement, rapidement, ou de façon irrégulière ?",
                I, "Texte", "Mises à jour automatiques sur les postes, plus lentes sur les serveurs",
            ),
            Question(
                "droits_administrateur", "Les utilisateurs sont-ils administrateurs de leur poste ?",
                "Si un utilisateur est « administrateur » de sa machine, un logiciel malveillant qu'il "
                "ouvre obtient aussi tous les droits. Limiter ces droits réduit fortement le risque.",
                I, "Oui / Non / partiel", "Non, sauf quelques exceptions techniques",
            ),
            Question(
                "mobiles_byod", "Des smartphones / tablettes accèdent-ils aux données pro ? Personnels ?",
                "L'usage d'appareils personnels (BYOD) pour le travail élargit la surface à protéger. "
                "Précisez s'ils sont gérés (MDM) ou non.",
                I, "Texte", "Téléphones pro gérés ; pas d'accès depuis les téléphones personnels",
            ),
        ),
    ),
    Section(
        "donnees", "9. Données personnelles (RGPD)",
        "Cette partie concerne les données relatives à des personnes (clients, patients, salariés). "
        "Le RGPD impose des obligations précises et prévoit des sanctions.",
        (
            Question(
                "donnees_personnelles_traitees", "Traitez-vous des données personnelles ?",
                "Toute information se rapportant à une personne identifiable (nom, email, dossier, "
                "numéro). Presque toutes les organisations en traitent.",
                C, "Oui / Non", "Oui",
            ),
            Question(
                "categories_donnees_personnelles", "Quelles catégories de données personnelles ?",
                "Précisez les types (clients, salariés, prospects) et surtout les données « sensibles » "
                "(santé, biométrie, opinions), plus strictement encadrées par la loi.",
                I, "Liste", "Patients (données de santé), salariés, prospects",
                depends_on_true="donnees_personnelles_traitees",
            ),
            Question(
                "volumes_personnes", "Combien de personnes concernées environ ?",
                "Un ordre de grandeur du nombre d'individus dont vous détenez les données. Un volume "
                "important augmente l'impact d'une fuite.",
                I, "Nombre", "~50 000 patients",
            ),
            Question(
                "transferts_hors_ue", "Des données sont-elles transférées hors Union Européenne ?",
                "Par exemple via un prestataire américain. Ces transferts nécessitent des garanties "
                "juridiques particulières sous le RGPD.",
                I, "Oui / Non + détails", "Oui, support d'un éditeur hébergé aux États-Unis",
            ),
            Question(
                "registre_traitements", "Tenez-vous un registre des traitements et avez-vous un DPO ?",
                "Le registre liste vos usages de données personnelles ; le DPO est le référent RGPD. "
                "Tous deux sont des obligations pour beaucoup d'organisations.",
                I, "Texte", "Registre tenu par le DPO externe",
            ),
            Question(
                "sous_traitants_donnees", "Quels sous-traitants accèdent à des données personnelles ?",
                "Les prestataires qui manipulent vos données pour vous (hébergeur, éditeur SaaS, "
                "infogérance). Vous restez responsable de ce qu'ils en font.",
                I, "Liste", "Hébergeur HDS, éditeur du SIH, prestataire de paie",
            ),
            Question(
                "chiffrement_donnees", "Vos données sensibles sont-elles chiffrées ?",
                "Le chiffrement rend les données illisibles sans la clé. Précisez « au repos » (sur les "
                "disques/sauvegardes) et « en transit » (pendant les échanges réseau).",
                I, "Texte", "Chiffrement des sauvegardes et des échanges web ; disques serveurs non chiffrés",
            ),
        ),
    ),
    Section(
        "continuite", "10. Sauvegarde et continuité d'activité",
        "Votre capacité à résister à une panne, une destruction ou un rançongiciel.",
        (
            Question(
                "sauvegarde_strategie", "Quelle est votre stratégie de sauvegarde ?",
                "À quelle fréquence sauvegardez-vous ? Existe-t-il une copie « hors ligne » ou "
                "« immuable » (que même un attaquant ne peut effacer) ? C'est la dernière défense "
                "contre un rançongiciel.",
                C, "Texte", "Sauvegarde quotidienne, avec une copie hors ligne hebdomadaire",
            ),
            Question(
                "tests_restauration", "Testez-vous régulièrement la restauration des sauvegardes ?",
                "Une sauvegarde jamais testée peut se révéler illisible le jour où on en a besoin. "
                "Indiquez si et à quelle fréquence vous vérifiez qu'elle fonctionne.",
                I, "Texte", "Test de restauration semestriel",
            ),
            Question(
                "plan_continuite", "Avez-vous un plan de continuité / reprise d'activité (PCA/PRA) ?",
                "Un document et une organisation prévus pour continuer ou redémarrer l'activité après un "
                "sinistre majeur (incendie, cyberattaque).",
                I, "Oui / Non + détails", "PRA informatique en place, PCA métier en cours",
            ),
            Question(
                "rto_rpo", "Combien de temps pouvez-vous rester à l'arrêt, et quelle perte de données tolérez-vous ?",
                "En clair : au bout de combien de temps l'arrêt devient-il critique (RTO), et jusqu'à "
                "combien d'heures de données pouvez-vous perdre (RPO) ? Une estimation suffit.",
                I, "Texte", "Arrêt tolérable ~4h, perte de données max ~1h",
            ),
        ),
    ),
    Section(
        "detection", "11. Journalisation, détection et incidents",
        "Votre capacité à voir ce qui se passe et à réagir.",
        (
            Question(
                "journalisation", "Conservez-vous des journaux (logs) des activités système ?",
                "Les journaux enregistrent les connexions et actions. Ils sont indispensables pour "
                "comprendre une attaque après coup. Précisez leur durée de conservation.",
                I, "Texte", "Journaux conservés 6 mois sur les serveurs principaux",
            ),
            Question(
                "supervision_securite", "Surveillez-vous activement les alertes de sécurité (SIEM/SOC) ?",
                "Un SIEM centralise les alertes ; un SOC est l'équipe qui les surveille en continu. "
                "Beaucoup d'organisations n'en ont pas — dites simplement l'état réel.",
                I, "Texte", "Pas de SOC ; alertes Defender consultées ponctuellement",
            ),
            Question(
                "incidents_securite_passes", "Avez-vous déjà subi des incidents de sécurité notables ?",
                "Virus, rançongiciel, fuite de données, intrusion, fraude… Même anciens, ils renseignent "
                "sur votre exposition. Aucune honte : l'objectif est d'apprendre.",
                I, "Texte", "Une tentative de rançongiciel bloquée en 2023",
            ),
            Question(
                "plan_reponse_incident", "Disposez-vous d'une procédure de réponse aux incidents ?",
                "Qui appeler, quoi faire, dans quel ordre en cas de crise cyber. Et avez-vous un contact "
                "d'assistance (prestataire, assurance cyber, CERT) ?",
                I, "Texte", "Procédure informelle ; contrat d'assistance avec un prestataire",
            ),
        ),
    ),
    Section(
        "ecosysteme", "12. Écosystème et tiers de confiance",
        "Vos dépendances envers d'autres organisations — souvent une porte d'entrée des attaques.",
        (
            Question(
                "fournisseurs_tiers_critiques", "Quels sont vos fournisseurs / prestataires critiques ?",
                "Ceux dont une panne ou un piratage vous impacterait directement (hébergeur, éditeur, "
                "infogérant, fournisseur d'énergie). L'attaque passe souvent par eux.",
                C, "Liste", "Hébergeur HDS, éditeur du SIH, prestataire d'infogérance",
            ),
            Question(
                "infogerance", "Une partie de votre informatique est-elle infogérée / externalisée ?",
                "Confiez-vous la gestion de vos systèmes à un prestataire externe ? Si oui, il a des accès "
                "étendus qu'il faut encadrer.",
                I, "Texte", "Infogérance partielle des serveurs par un prestataire local",
            ),
            Question(
                "clauses_securite_contrats", "Vos contrats prestataires incluent-ils des exigences de sécurité ?",
                "Des engagements écrits (confidentialité, notification en cas d'incident, droit d'audit). "
                "Sans clause, vous avez peu de recours.",
                I, "Texte", "Clauses RGPD présentes, exigences de sécurité limitées",
            ),
        ),
    ),
    Section(
        "physique_rh", "13. Sécurité physique et facteur humain",
        "Les locaux et les personnes comptent autant que la technique.",
        (
            Question(
                "securite_physique", "Comment sont protégés vos locaux et salles serveurs ?",
                "Contrôle d'accès (badges), vidéosurveillance, salle informatique fermée, protection "
                "contre l'incendie et les coupures électriques.",
                I, "Texte", "Badges, salle serveurs fermée à clé, onduleurs",
            ),
            Question(
                "sensibilisation", "Vos collaborateurs sont-ils sensibilisés à la cybersécurité ?",
                "Formations, campagnes de faux e-mails piégés (phishing), charte informatique. L'humain "
                "est la cible la plus fréquente des attaques.",
                I, "Texte", "Sensibilisation annuelle, pas de test de phishing",
            ),
            Question(
                "charte_informatique", "Existe-t-il une charte informatique et des politiques de sécurité écrites ?",
                "Des documents qui fixent les règles d'usage et de sécurité, connus des employés.",
                I, "Oui / Non + détails", "Charte signée à l'embauche ; PSSI en cours de rédaction",
            ),
        ),
    ),
    Section(
        "conformite", "14. Conformité, référentiels et historique",
        "Les cadres réglementaires et normatifs qui s'appliquent, et ce qui a déjà été fait.",
        (
            Question(
                "applicable_frameworks", "Quels référentiels / réglementations s'appliquent à vous ?",
                "Les cadres de sécurité et lois applicables. Pré-remplis : ISO 27001, guide d'hygiène "
                "ANSSI, RGPD, NIST. Confirmez, retirez, ou ajoutez (ex. HDS, HIPAA, PCI-DSS, NIS2).",
                C, "Liste", "ISO27001, ANSSI_hygiene, RGPD, NIST, HDS",
            ),
            Question(
                "certifications_obtenues", "Détenez-vous déjà des certifications ou labels de sécurité ?",
                "Par exemple ISO 27001, HDS, SecNumCloud. Précisez leur périmètre et leur validité.",
                I, "Texte", "Certification HDS de l'hébergeur ; pas de certification propre",
            ),
            Question(
                "audits_anterieurs", "Des audits, tests d'intrusion ou évaluations ont-ils déjà eu lieu ?",
                "Tout travail antérieur (audit ANSSI, pentest, évaluation interne) et ses grandes "
                "conclusions. Cela évite de repartir de zéro.",
                I, "Texte", "Audit de maturité ANSSI en 2023, quelques écarts identifiés",
            ),
            Question(
                "documents_fournis", "Quels documents joignez-vous à ce questionnaire ? (facultatif)",
                "Tout document utile : politique de sécurité, schéma réseau, inventaire, rapport d'audit "
                "précédent, registre RGPD. C'est facultatif mais très utile — l'agent les lira et en "
                "extraira les informations, en citant ses sources.",
                I, "Liste de fichiers", "PSSI.pdf, schema_reseau.pdf, rapport_audit_2023.pdf",
                askable=False,
            ),
        ),
    ),
)


def all_questions() -> tuple[Question, ...]:
    return tuple(q for section in QUESTIONNAIRE for q in section.questions)


def question_by_id() -> dict[str, Question]:
    return {q.id: q for q in all_questions()}
