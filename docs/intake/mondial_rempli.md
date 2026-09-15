QUESTIONNAIRE DE CONTEXTE — AUDIT EBIOS RISK MANAGER
Organisation auditée : Mondial-Tickets
Réponses renseignées à partir de l'étude de cas fournie (« Mondial-Tickets — Étude de Cas ISO 27001:2022 »)
Méthodologie
Chaque réponse ci-dessous est déduite exclusivement du contenu de l'étude de cas « Mondial-Tickets — Étude de Cas ISO 27001:2022 » fournie en pièce jointe. Les sections et pages sont référencées entre parenthèses (ex. §2.1, §4.1) pour permettre la vérification.
Aucune information n'a été inventée, supposée ou extrapolée. Lorsque l'étude de cas ne fournit pas d'élément permettant de répondre à une question, la mention « Information non disponible dans le document fourni. » est indiquée explicitement, parfois complétée par les éléments de contexte factuels les plus proches disponibles dans le document, clairement distingués de toute déduction.
Un second document a été fourni en amont, un modèle de « Questionnaire de contexte — Audit EBIOS Risk Manager » vierge : c'est sa structure (15 sections, une question par ligne) qui a été reprise et complétée ci-dessous.
 
1. Identité et gouvernance de l'organisation
Répond : DIRECTION
Q. Quel est le nom de l'organisation auditée ?
R. Mondial-Tickets (source : page de garde ; §1.1 Contexte & Activité).
Q. Quelle est sa forme juridique et son statut ?
R. Information non disponible dans le document fourni. Le document désigne Mondial-Tickets comme une « société » (§1.1), sans préciser sa forme juridique (SA, SAS…) ni si elle est indépendante ou filiale d'un groupe.
Q. Quel est le secteur d'activité principal ?
R. Billetterie en ligne, spécifiquement la vente de billets pour de grands événements sportifs internationaux (page de garde ; §1.1).
Q. Décrivez en quelques phrases votre activité et vos missions.
R. Société fondée en 2005, pionnière de la vente en ligne de billets pour de grands événements sportifs internationaux (Coupes du Monde de football et de rugby, Tournoi des 6 Nations, Euro 2024, championnats nationaux). Elle détient des droits de revente officiels acquis auprès des instances sportives FIFA, IRB (World Rugby) et FFF, et distribue exclusivement via le site www.mondial-tickets.com (§1.1, §1.2).
Q. Quel est l'effectif total (nombre de personnes) ?
R. ~50 collaborateurs au total : 35 à Paris (siège) et 15 à Berlin (filiale) (page de garde ; §3.1, §3.2).
Q. Sur quels pays / sites l'audit porte-t-il ?
R. France (Paris, siège social) et Allemagne (Berlin, filiale opérationnelle) (§1.1).
Q. Qui est responsable de la sécurité de l'information ?
R. Aucun RSSI n'est désigné à ce jour ; ce point est explicitement qualifié de « critique » dans le document (§3.2). R. Zipet a été mandaté par la direction comme « Responsable Projet SMSI », sous l'autorité de V. Brugidoux, Directrice Informatique (§3.1, §5.1). Aucun DPO n'est mentionné.
Q. Comment évalueriez-vous votre maturité en cybersécurité ?
R. Aucune auto-évaluation qualitative n'est formulée par l'entreprise dans le document. Éléments factuels disponibles : absence de RSSI, absence de politique de sécurité formalisée (§3.2), référentiel SMSI « en cours de constitution » (§5.1).
Q. Avez-vous déjà formalisé une analyse de risques, et qui l'a validée ?
R. Oui : le référentiel SMSI en cours de constitution mentionne « l'analyse des risques (dernière version : 2023) » (§5.1). Le document ne précise ni qui l'a validée, ni si elle a été revue depuis 2023.
2. Périmètre et objectifs de l'audit
Répond : DIRECTION
Q. Quels sont vos objectifs pour cet audit ?
R. Obtenir la certification ISO/IEC 27001:2022 (page de garde, « Norme cible »). Le déclencheur du projet SMSI est l'incident de fiabilité survenu pendant la Coupe du Monde de rugby 2011 en pic de charge (§1.3). Les priorités identifiées à l'issue de l'analyse de risques sont : PCA/PRA, protection des données personnelles, gestion des incidents de sécurité, clarification des rôles et responsabilités, gestion documentaire du SMSI (§5.2).
Q. Quels systèmes / services sont DANS le périmètre ?
R. Information non disponible dans le document fourni. La définition du périmètre du SMSI fait explicitement l'objet d'une question ouverte de l'étude de cas (« proposez le périmètre (scope) du SMSI ») : elle n'est donc pas encore arrêtée par l'entreprise.
Q. Quels systèmes / services sont explicitement HORS périmètre ?
R. Information non disponible dans le document fourni. Pour la même raison que ci-dessus, aucune exclusion n'est formulée par l'entreprise.
Q. Qu'est-ce qui est en train de changer, ou va changer bientôt ?
R. Aucun changement technique/SI n'est explicitement annoncé (pas de migration, fusion ou changement de prestataire mentionné). Le document décrit en revanche des ambitions de croissance commerciale : Tournoi des 6 Nations, Euro 2024, Coupes du Monde 2026/2030/2034, Championnat de France de rugby (dès 2025), championnats nationaux France/Allemagne (dès 2025) et autres ligues européennes (dès 2027), ainsi que des « ouvertures potentielles d'agences locales selon opportunités de marché » (§1.2).
Q. Qui commandite l'audit et qui décidera in fine ?
R. La direction de Mondial-Tickets a mandaté R. Zipet comme Responsable Projet SMSI (§5.1). Le Directeur Général est P. Aknine (§3.1). Aucun sponsor nommément désigné pour l'audit ISO 27001 n'est précisé au-delà de « la direction ».
Q. Existe-t-il des contraintes de calendrier ou d'échéance ?
R. Information non disponible dans le document fourni.
3. Contexte métier et valeurs essentielles
Répond : DIRECTION + MÉTIERS
Q. Quels sont vos processus métier critiques ?
R. Le processus de vente en ligne de billets, décrit en 8 étapes (§4.1) : consultation/sélection des rencontres sportives, affichage des disponibilités et prix, gestion du panier (saisie nominative), contrôle anti-hooligan, paiement sécurisé, validation/enregistrement de la commande, génération et impression nominative des billets, expédition postale sous pli neutre.
Q. Quelles informations sont les plus sensibles / précieuses ?
R. Explicitement listées comme « Données Traitées — Criticité Élevée » (§4.1) : données d'identité des spectateurs (nom, prénom, n° de carte d'identité), données bancaires clients (n° de carte, autorisation de débit), liste anti-hooligan (identités de personnes fichées, qualifiée de CONFIDENTIELLE), données de commandes et de facturation, billets physiques sécurisés (hologramme, n° de série non prédictible), accusés de réception.
Q. Que se passerait-il si votre activité s'arrêtait une journée ?
R. Information non disponible dans le document fourni. Seul élément disponible : l'incident de 2011 (défaillances de fiabilité en pic de charge pendant la Coupe du Monde de rugby, en Nouvelle-Zélande) a été « le déclencheur du projet SMSI » (§1.3), ce qui atteste d'un impact suffisant pour motiver la démarche, sans détail chiffré des conséquences.
Q. Que se passerait-il si vos informations sensibles étaient divulguées ?
R. Information non disponible dans le document fourni. Le document indique seulement que la liste anti-hooligan constitue « une donnée à traitement particulier » nécessitant des mesures spécifiques au regard du RGPD (question ouverte Q4 de l'étude de cas), sans détailler l'impact d'une fuite.
Q. Que se passerait-il si vos données étaient modifiées à votre insu ?
R. Information non disponible dans le document fourni.
Q. À partir de quel moment un incident cesse-t-il d'être bénin pour vous ?
R. Information non disponible dans le document fourni.
Q. À partir de quel montant de perte un incident devient-il vraiment grave ?
R. Information non disponible dans le document fourni. Des ordres de grandeur financiers généraux sont fournis par ailleurs (§1.3) : ~350 000 billets vendus en 2 mois lors de la CM 2010, valeur moyenne unitaire de 150 € (grands événements) et 30 € (championnats nationaux), commission de 5 % du CA billetterie, CA potentiel annuel visé de ~900 000 € de commissions sur les championnats — mais aucun seuil de gravité n'est formulé.
Q. Parmi tout ce que vous avez cité, que faut-il protéger en priorité ?
R. Non formulé comme un classement des actifs. Le document liste en revanche des « Priorités SMSI Issues de l'Analyse de Risques » (§5.2), dans cet ordre : 1) PCA/PRA (risques liés aux pics de charge), 2) Protection des données personnelles, 3) Gestion et traitement des incidents de sécurité, 4) Clarification des rôles et responsabilités, 5) Gestion et contrôle documentaire du SMSI. Il s'agit de priorités de mise en œuvre du SMSI, pas d'un classement des actifs à protéger.
Q. Avez-vous des obligations de service ou contractuelles fortes ?
R. Mondial-Tickets détient des « droits de revente officiels acquis auprès des instances sportives : FIFA, IRB (World Rugby) et FFF » (§1.2), ce qui constitue une relation contractuelle formelle. Aucun engagement contractuel de disponibilité de service (SLA) chiffré n'est mentionné.
4. Cartographie du système d'information
Répond : TECHNIQUE
Q. Décrivez globalement votre système d'information.
R. Architecture décrite comme identique entre Paris et Berlin (§2.1), reposant sur 8 serveurs dédiés (réservation web, paiement web, base de données billetterie, éditique & courrier, comptabilité, gestion du personnel, messagerie Exchange, sauvegarde), des postes bureautiques Windows 10/11 avec Microsoft 365, l'application comptable SAGE, la messagerie Outlook/Exchange, et des portables itinérants connectés en VPN (§2.1, §2.3).
Q. Quelles sont vos principales applications métier ?
R. Plateforme de vente en ligne (serveurs web réservation + paiement), base de données Billetterie, application de comptabilité SAGE (sur base MSSQL), messagerie Microsoft Exchange/Outlook (§2.1, §2.3). Le document ne précise pas si ces applications sont internes ou fournies par un éditeur.
Q. Combien de serveurs et de postes de travail environ ?
R. 8 serveurs explicitement listés par site, Paris et Berlin ayant une « architecture identique » (§2.1) : réservation, paiement, base de données billetterie, éditique & courrier, comptabilité, gestion du personnel, messagerie Exchange, sauvegarde. Le nombre exact de postes de travail n'est pas donné ; seul l'effectif total (~50 collaborateurs, 35 à Paris + 15 à Berlin) permet d'en déduire un ordre de grandeur, sans être une donnée d'inventaire explicite.
Q. Tenez-vous un inventaire de votre matériel et de vos logiciels ?
R. Information non disponible dans le document fourni.
Q. Développez-vous des logiciels, et comment arrivent-ils en production ?
R. Information non disponible dans le document fourni.
Q. Quels systèmes d'exploitation utilisez-vous ?
R. Windows 10/11 pour les postes bureautiques (§2.3). Aucun système d'exploitation serveur n'est précisé. L'application SAGE fonctionne en client lourd sur base MSSQL (§2.1, §2.3).
Q. Utilisez-vous encore des systèmes anciens / non maintenus ?
R. Information non disponible dans le document fourni.
5. Hébergement et cloud
Répond : TECHNIQUE
Q. Comment est hébergé votre système d'information ?
R. Information non disponible dans le document fourni. (sur site / cloud / hybride non tranché explicitement). Les serveurs sont décrits comme des équipements physiques dédiés par site (ex. « Serveur de Sauvegarde HP »), ce qui suggère une infrastructure localisée dans les locaux de Paris et Berlin, mais le document n'emploie jamais le terme « hébergement » pour trancher entre sur site, cloud ou hybride.
Q. Quels fournisseurs cloud et services en ligne utilisez-vous ?
R. Microsoft 365 est utilisé pour la suite bureautique (§2.3). Aucun autre fournisseur cloud (AWS, Azure, hébergeur dédié) n'est mentionné.
Q. Où sont physiquement stockées vos données ?
R. Non précisé en tant que tel ; les seules localisations mentionnées dans le document sont les deux sites physiques de l'entreprise, Paris et Berlin (§1.1, §2.1).
Q. Vos hébergeurs ont-ils des certifications de sécurité ?
R. Information non disponible dans le document fourni.
6. Réseau et accès distant
Répond : TECHNIQUE
Q. Comment votre réseau est-il organisé ?
R. Éléments partiels disponibles : le « Serveur de Gestion du Personnel » est explicitement décrit comme « isolé réseau, non connecté aux autres machines » (§2.1), ce qui indique une forme de segmentation pour cet actif spécifique. « Aucun réseau Wi-Fi déployé sur les sites » (§2.3). Aucune description globale de zones réseau (bureautique / serveurs / DMZ) n'est fournie au-delà de ces deux éléments.
Q. Quels services sont accessibles depuis Internet ?
R. Le « Serveur WEB de réservation » est explicitement « exposé sur Internet, point d'entrée clients » (§2.1). Le site www.mondial-tickets.com constitue l'interface de réservation pour le grand public (§1.2, §2.2).
Q. Qui travaille à distance, et depuis quel matériel ?
R. Des « portables itinérants » sont mentionnés, avec VPN obligatoire (§2.3), mais les profils exacts de collaborateurs concernés (commerciaux, correspondants, direction…) ne sont pas précisés.
Q. Par quels moyens accède-t-on à distance au système ?
R. VPN obligatoire pour les portables itinérants, connexion Wi-Fi + Ethernet (§2.3). Aucune mention de MFA ou de VDI dans le document.
Q. Disposez-vous de réseaux Wi-Fi, et sont-ils séparés (invités / interne) ?
R. Explicitement absent : « Aucun réseau Wi-Fi déployé sur les sites » (§2.3) — la question de la séparation invité/interne ne se pose donc pas.
Q. Avez-vous des connexions permanentes avec des partenaires ?
R. Table des interconnexions et partenaires externes (§2.2) : Ministère de l'Intérieur (France/Allemagne) — liste anti-hooligan confidentielle ; Partenaire bancaire — autorisation de paiement en temps réel ; FIFA / IRB / FFF — disponibilités, prix, conditions de vente ; Filiale Berlin ↔ Paris — synchronisation de la base de données billetterie ; Internet (grand public) — interface de réservation clients.
7. Identités et gestion des accès
Répond : TECHNIQUE
Q. Comment gérez-vous les comptes utilisateurs ?
R. Information non disponible dans le document fourni.
Q. Qui vérifie, et à quelle fréquence, que chacun n'a que les accès nécessaires ?
R. Information non disponible dans le document fourni.
Q. L'authentification multifacteur (MFA) est-elle en place ?
R. Information non disponible dans le document fourni.
Q. Comment sont gérés les comptes à privilèges (administrateurs) ?
R. Information non disponible dans le document fourni.
Q. Quelle est votre politique de mots de passe ?
R. Information non disponible dans le document fourni.
8. Postes de travail et serveurs
Répond : TECHNIQUE
Q. Quel antivirus / EDR est déployé ?
R. Information non disponible dans le document fourni.
Q. Comment appliquez-vous les mises à jour de sécurité (correctifs) ?
R. Information non disponible dans le document fourni.
Q. Qui est administrateur de son propre poste, et pourquoi ?
R. Information non disponible dans le document fourni.
Q. Comment sont gérés les smartphones et tablettes fournis par l'entreprise ?
R. Information non disponible dans le document fourni.
Q. Des appareils personnels accèdent-ils aux données professionnelles ?
R. Information non disponible dans le document fourni.
Q. Comment repérez-vous les failles connues de vos systèmes ?
R. Information non disponible dans le document fourni.
9. Données personnelles (RGPD)
Répond : RSSI / DSI
Q. Sur quelles personnes détenez-vous des informations ?
R. Les spectateurs/clients acheteurs de billets, le personnel de l'entreprise (existence d'un « Serveur de Gestion du Personnel », §2.1), et les personnes figurant sur la liste anti-hooligan transmise par le Ministère de l'Intérieur (§2.2, §4.1) — ces dernières ne sont pas des personnes dont Mondial-Tickets collecte directement les données, mais leurs données sont consultées par l'entreprise dans le cadre du contrôle anti-hooligan.
Q. Quelles catégories de données personnelles ?
R. Données d'identité des spectateurs (nom, prénom, n° de carte d'identité), données bancaires clients, liste anti-hooligan (identités de personnes fichées, qualifiée de confidentielle et de donnée à traitement particulier), données de commandes/facturation (§4.1). Aucune donnée RH détaillée n'est décrite au-delà de l'existence d'un « Serveur de Gestion du Personnel » (§2.1).
Q. Combien de personnes concernées environ ?
R. Information non disponible dans le document fourni. Seul indicateur disponible : ~350 000 billets vendus en 2 mois lors de la Coupe du Monde 2010 (§1.3), qui donne un ordre de grandeur du volume de transactions traitées, mais pas du nombre de personnes physiques distinctes.
Q. Des données sont-elles transférées hors Union Européenne ?
R. Information non disponible dans le document fourni.
Q. Tenez-vous un registre des activités de traitement ?
R. Information non disponible dans le document fourni.
Q. Avez-vous désigné un délégué à la protection des données (DPO) ?
R. Information non disponible dans le document fourni.
Q. Combien de temps conservez-vous les données, et comment sont-elles supprimées ?
R. Un seul élément explicite : « Accusés de réception : conservés 3 mois post-événement » (§4.1). Aucune autre durée de conservation (données clients, bancaires, liste anti-hooligan) n'est précisée, ni les modalités de suppression.
Q. Quels sous-traitants accèdent à des données personnelles ?
R. Le partenaire bancaire traite les données de paiement pour l'autorisation en temps réel (§2.2). Le Ministère de l'Intérieur transmet la liste anti-hooligan (§2.2) — relation qui relève davantage d'une fourniture de données que d'une sous-traitance au sens RGPD. Aucun autre sous-traitant (hébergeur, éditeur SaaS) n'est nommément identifié dans le document.
Q. Vos données sensibles sont-elles chiffrées ?
R. Information non disponible dans le document fourni. Seul indice disponible : le « Serveur WEB de paiement » est décrit comme connecté à la gestion comptable via des « flux sécurisés » (§2.1). Aucune précision n'est donnée sur le chiffrement au repos (disques, bases de données, sauvegardes).
10. Sauvegarde et continuité d'activité
Répond : RSSI / DSI
Q. Quelle est votre stratégie de sauvegarde ?
R. « Sauvegardes hebdomadaires automatisées — complètes, incrémentielles, différentielles » via le Serveur de Sauvegarde HP (§2.1, §4.2), avec « duplication inter-sites Paris ↔ Berlin » (§4.2). Aucune mention de copie hors ligne ou immuable.
Q. Testez-vous régulièrement la restauration des sauvegardes ?
R. Le plan de sauvegarde mentionne des « tests de restauration et plans de secours », ainsi que le « test des fonctions de haute disponibilité » comme éléments du plan (§4.2), mais sans préciser une fréquence réelle ni la date du dernier test effectué.
Q. Avez-vous un plan de reprise informatique (PRA) ?
R. Non formalisé à ce jour d'après le document : l'élaboration d'un PRA fait explicitement l'objet d'une question ouverte de l'étude de cas (Q14 : « Élaborez un Plan de Continuité d'Activité (PCA) et un Plan de Reprise d'Activité (PRA) »), ce qui indique qu'aucun PRA documenté n'existe encore.
Q. Avez-vous un plan de continuité métier (PCA) ?
R. Même constat que pour le PRA : non formalisé, son élaboration fait l'objet de la même question ouverte Q14 de l'étude de cas.
Q. Combien de temps pouvez-vous rester à l'arrêt, et quelle perte de données tolérez-vous ?
R. Non définis dans le document ; leur définition (RTO et RPO cibles) est explicitement demandée dans la question ouverte Q14 de l'étude de cas.
11. Journalisation, détection et incidents
Répond : RSSI / DSI
Q. Conservez-vous des journaux (logs) des activités système ?
R. Information non disponible dans le document fourni.
Q. Surveillez-vous activement les alertes de sécurité (SIEM/SOC) ?
R. Information non disponible dans le document fourni.
Q. Avez-vous déjà subi des incidents de sécurité notables ?
R. Un incident réel est explicitement mentionné : lors de la Coupe du Monde de rugby 2011 en Nouvelle-Zélande, « des défaillances de fiabilité sur la plateforme de vente en ligne ont été constatées en pic de charge », ce qui a déclenché le projet SMSI (§1.3). À noter : le scénario de « billets frauduleux » et de « données clients exfiltrées » mentionné dans la question ouverte Q15 de l'étude de cas est un scénario fictif proposé pour l'exercice pédagogique, et non un incident réellement survenu — il ne doit pas être confondu avec l'incident réel de 2011.
Q. Disposez-vous d'une procédure de réponse aux incidents ?
R. Information non disponible dans le document fourni. Cette absence est cohérente avec l'absence de RSSI et de politique de sécurité formalisée relevée par ailleurs (§3.2).
Q. En cas de violation de données, qui devez-vous prévenir et sous quel délai ?
R. Information non disponible dans le document fourni.
12. Écosystème et tiers de confiance
Répond : DIRECTION / ACHATS
Q. Quels sont vos fournisseurs / prestataires critiques ?
R. Partenaire bancaire (autorisation de paiement en temps réel), Ministère de l'Intérieur France et Ministère fédéral de l'Intérieur allemand (liste anti-hooligan), instances sportives FIFA / IRB (World Rugby) / FFF (droits de revente, disponibilités, prix, conditions de vente) (§1.2, §2.2). Le fournisseur du serveur de sauvegarde (HP) est mentionné comme marque d'équipement, sans être décrit comme prestataire de service géré.
Q. Une partie de votre informatique est-elle infogérée / externalisée ?
R. Information non disponible dans le document fourni.
Q. Vos contrats prestataires incluent-ils des exigences de sécurité ?
R. Information non disponible dans le document fourni.
13. Sécurité physique et facteur humain
Répond : RSSI / DSI
Q. Comment sont protégés vos locaux et salles serveurs ?
R. Information non disponible dans le document fourni.
Q. Vos collaborateurs sont-ils sensibilisés à la cybersécurité ?
R. Information non disponible dans le document fourni.
Q. Existe-t-il une charte informatique et des politiques de sécurité écrites ?
R. Explicitement absentes à ce jour : « il n'existe à ce jour aucun Responsable de la Sécurité des Systèmes d'Information (RSSI) désigné, et aucune politique de sécurité formalisée n'a été adoptée » (§3.2). Aucune charte informatique n'est mentionnée dans le document.
14. Sources de menace et scénarios redoutés
Répond : DIRECTION / RSSI
Q. Selon vous, qui pourrait chercher à vous attaquer, et pourquoi ?
R. Information non disponible dans le document fourni. (l'entreprise ne formule pas elle-même d'évaluation des sources de menace — c'est précisément l'objet de l'Atelier 2 EBIOS RM à construire). Éléments de contexte factuels pouvant éclairer cette réflexion, sans constituer une déclaration de l'entreprise : présence de données bancaires et d'identité (§4.1), détention d'une liste anti-hooligan confidentielle transmise par les ministères de l'Intérieur (§2.2, §4.1), incident de disponibilité déjà vécu en 2011 en pic de charge (§1.3).
Q. Par quel chemin une attaque arriverait-elle le plus probablement ?
R. Information non disponible dans le document fourni.
15. Conformité, référentiels et historique
Répond : DIRECTION / RSSI
Q. Quels référentiels / réglementations s'appliquent à vous ?
R. ISO/IEC 27001:2022 est explicitement la norme cible (page de garde). Le RGPD est mentionné en lien avec le traitement des données sensibles (question ouverte Q4 de l'étude de cas, « exigences du RGPD »). Aucun autre référentiel (ANSSI, NIST, HDS…) n'est cité dans le document.
Q. Détenez-vous déjà des certifications ou labels de sécurité ?
R. Non explicitement affirmé, mais le document présente l'ISO/IEC 27001:2022 comme la « norme cible » (page de garde), c'est-à-dire un objectif à atteindre — ce qui implique que Mondial-Tickets ne la détient pas encore. Aucune autre certification ou label n'est mentionné.
Q. Des audits, tests d'intrusion ou évaluations ont-ils déjà eu lieu ?
R. Information non disponible dans le document fourni.
Q. Quels documents joignez-vous à ce questionnaire ?
R. Le seul document exploité pour renseigner ce questionnaire est l'étude de cas « Mondial-Tickets — Étude de Cas ISO 27001:2022 » (12 pages, © 2024, auteur Jamal SAAD). Aucun autre document (schéma réseau, inventaire, rapport d'audit antérieur, PSSI, registre RGPD) n'a été communiqué.
