# Questionnaire de contexte — Audit EBIOS Risk Manager

**À l'attention de la personne qui remplit ce document**

Ce questionnaire recueille les informations nécessaires pour cadrer votre audit de
sécurité selon la méthode EBIOS Risk Manager. Il est **volontairement complet** :
prenez le temps qu'il faut, et n'hésitez pas à répondre « je ne sais pas » quand
c'est le cas — c'est une information utile en soi.

**Vous n'avez pas besoin d'être informaticien pour répondre.** Chaque question est
accompagnée d'une explication en langage simple. Répondez avec vos mots.

Comment lire chaque question :

- 🔹 **Explication** : ce que la question signifie, sans jargon.
- 🔸 **Priorité** : « Critique » = nous ne pouvons pas démarrer sans cette réponse ;
  « Important » = si vous ne savez pas, dites-le et expliquez brièvement pourquoi.
- ✏️ **Votre réponse** : écrivez juste en dessous.

Toute réponse que vous écrivez est considérée comme une **déclaration** de votre
part. Vous pouvez joindre des documents (politique de sécurité, schéma réseau,
inventaire, rapport d'audit précédent…) : c'est facultatif, mais l'agent les lira
et en extraira les informations en citant précisément ses sources. Rien ne sera
supposé ou inventé à votre place — les informations manquantes vous seront
redemandées.

---

## 1. Identité et gouvernance de l'organisation

*Cette première partie décrit qui vous êtes et comment la sécurité est organisée chez vous. Elle sert à cadrer toute l'étude.*

### Quel est le nom de l'organisation auditée ?
🔹 **Explication.** Le nom officiel de l'entité concernée par l'audit (société, établissement, direction).

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte.
Exemple : _Clinique du Val Fleuri_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quelle est sa forme juridique et son statut ?
🔹 **Explication.** S'agit-il d'une entreprise privée, d'une association, d'un établissement public, d'une filiale d'un groupe ? Cela influence les obligations réglementaires.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _SAS privée, filiale d'un groupe de santé_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quel est le secteur d'activité principal ?
🔹 **Explication.** Le domaine dans lequel vous opérez (santé, finance, industrie, service public…). Le secteur détermine les menaces typiques et les référentiels applicables.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte.
Exemple : _Santé — établissement de soins privé_

✏️ **Votre réponse :**

> _______________________________________________________________

### Décrivez en quelques phrases votre activité et vos missions.
🔹 **Explication.** Expliquez simplement ce que fait l'organisation au quotidien et pour qui. Aucune connaissance technique n'est requise ici.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _Prise en charge médicale de patients en hospitalisation et consultations externes._

✏️ **Votre réponse :**

> _______________________________________________________________

### Quel est l'effectif total (nombre de personnes) ?
🔹 **Explication.** Le nombre approximatif de personnes travaillant dans l'organisation (salariés, intérimaires, prestataires permanents). Cela donne une idée de la taille du système.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Nombre.
Exemple : _420_

✏️ **Votre réponse :**

> _______________________________________________________________

### Sur quels pays / sites l'audit porte-t-il ?
🔹 **Explication.** Listez les lieux (villes, pays, sites) concernés par l'étude. Un site à l'étranger peut impliquer d'autres lois.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _France (siège de Lyon, site de Grenoble)_

✏️ **Votre réponse :**

> _______________________________________________________________

### Qui est responsable de la sécurité de l'information ?
🔹 **Explication.** Existe-t-il un RSSI (Responsable de la Sécurité des Systèmes d'Information), un DSI, un DPO (délégué à la protection des données) ? Un RSSI pilote la cybersécurité ; un DPO veille au respect de la loi sur les données personnelles.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Un RSSI à temps partiel et un DPO externe mutualisé_

✏️ **Votre réponse :**

> _______________________________________________________________

### Comment évalueriez-vous votre maturité en cybersécurité ?
🔹 **Explication.** Votre ressenti global : débutante, en cours de structuration, mature. Il n'y a pas de mauvaise réponse — cela nous aide à calibrer nos attentes.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Choix / texte.
Exemple : _En cours de structuration_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous déjà formalisé une analyse de risques, et qui l'a validée ?
🔹 **Explication.** Un document qui recense vos risques, les décisions prises et par qui elles ont été approuvées. C'est ce qui permet de démontrer que la sécurité est pilotée et non subie. Précisez la date de la dernière mise à jour.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Analyse de 2022 validée en comité de direction, non revue depuis_

✏️ **Votre réponse :**

> _______________________________________________________________


## 2. Périmètre et objectifs de l'audit

*Ici nous délimitons précisément ce qui est étudié et pourquoi.*

### Quels sont vos objectifs pour cet audit ?
🔹 **Explication.** Ce que vous attendez concrètement : obtenir une certification, répondre à une exigence d'un client, réduire un risque connu, préparer une mise en conformité…

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _Se mettre en conformité et réduire le risque de fuite de données patients_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels systèmes / services sont DANS le périmètre ?
🔹 **Explication.** La liste de ce qui doit être analysé (applications, sites, activités). Tout ce qui n'est pas listé sera considéré hors périmètre.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _SIH, imagerie, messagerie, accès distant des médecins_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels systèmes / services sont explicitement HORS périmètre ?
🔹 **Explication.** Ce que vous souhaitez volontairement exclure de l'étude, et si possible pourquoi. Une exclusion doit être un choix conscient, jamais un oubli.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste + justification.
Exemple : _La billetterie de la cafétéria (sans donnée sensible)_

✏️ **Votre réponse :**

> _______________________________________________________________

### Qui commandite l'audit et qui décidera in fine ?
🔹 **Explication.** La ou les personnes qui portent le projet et qui approuveront les conclusions (direction, comité, sponsor). L'audit assiste la décision, mais la décision reste humaine.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _La Direction Générale et le Directeur des Systèmes d'Information_

✏️ **Votre réponse :**

> _______________________________________________________________

### Existe-t-il des contraintes de calendrier ou d'échéance ?
🔹 **Explication.** Une date butoir (audit client, renouvellement de certification, échéance réglementaire) qui structure le planning.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Certification HDS à renouveler en mars prochain_

✏️ **Votre réponse :**

> _______________________________________________________________


## 3. Contexte métier et valeurs essentielles

*Cette partie identifie ce qui est vital pour votre organisation — le cœur de l'analyse EBIOS RM. Répondez du point de vue métier, pas informatique.*

### Quels sont vos processus métier critiques ?
🔹 **Explication.** Les activités sans lesquelles l'organisation ne peut pas fonctionner. Pensez : « si cela s'arrête, nous sommes bloqués ». Ce sont les futurs 'biens essentiels' de l'étude.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _Prise en charge des patients, gestion du dossier médical, imagerie_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quelles informations sont les plus sensibles / précieuses ?
🔹 **Explication.** Les données dont la fuite, la perte ou l'altération serait grave (données clients, secrets de fabrication, données de santé, données financières).

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _Dossiers médicaux, résultats d'examens, données RH_

✏️ **Votre réponse :**

> _______________________________________________________________

### Que se passerait-il si votre activité s'arrêtait une journée ?
🔹 **Explication.** Décrivez les conséquences concrètes d'une INTERRUPTION (sécurité des personnes, pertes financières, atteinte à l'image, conséquences légales). Précisez à partir de quelle durée les conséquences changent de nature. Cela nourrit la gravité des événements redoutés.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _Report de soins, risque pour les patients, perte de revenus, atteinte à la réputation_

✏️ **Votre réponse :**

> _______________________________________________________________

### Que se passerait-il si vos informations sensibles étaient divulguées ?
🔹 **Explication.** Une FUITE n'a pas les mêmes conséquences qu'une panne : imaginez vos informations les plus sensibles rendues publiques ou vendues. Qui serait lésé, quelles obligations légales s'appliqueraient, quel serait le préjudice pour les personnes concernées ?

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _Atteinte grave à la vie privée des patients, notification CNIL et information des personnes, plaintes et perte de confiance durable_

✏️ **Votre réponse :**

> _______________________________________________________________

### Que se passerait-il si vos données étaient modifiées à votre insu ?
🔹 **Explication.** Une ALTÉRATION est souvent le scénario le plus grave et le moins visible : des données fausses utilisées comme si elles étaient justes. Pensez à une décision prise sur une donnée erronée, ou à une falsification que personne ne détecte.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _Erreur de prescription sur un dossier falsifié, mise en danger du patient, perte de valeur probante du dossier médical_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous des obligations de service ou contractuelles fortes ?
🔹 **Explication.** Des engagements envers vos clients ou l'État (continuité de service, délais, disponibilité garantie) que la sécurité doit préserver.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Continuité des soins 24/7, engagements de disponibilité envers l'ARS_

✏️ **Votre réponse :**

> _______________________________________________________________


## 4. Cartographie du système d'information

*Une vue d'ensemble de votre informatique. Restez simple : nous approfondirons si besoin.*

### Décrivez globalement votre système d'information.
🔹 **Explication.** Un résumé libre : vos principales applications, où elles tournent, comment les gens travaillent. Comme si vous l'expliquiez à un nouveau collègue.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte libre.
Exemple : _SIH central, messagerie Microsoft 365, imagerie PACS, postes Windows_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quelles sont vos principales applications métier ?
🔹 **Explication.** Les logiciels essentiels à votre activité, avec leur rôle (par ex. logiciel de gestion, outil de production, ERP). Précisez s'ils sont internes ou fournis par un éditeur.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _SIH (éditeur X), PACS imagerie (éditeur Y), paie (SaaS)_

✏️ **Votre réponse :**

> _______________________________________________________________

### Combien de serveurs et de postes de travail environ ?
🔹 **Explication.** Un ordre de grandeur suffit. Cela indique la surface à protéger.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Nombres.
Exemple : _~30 serveurs, ~350 postes_

✏️ **Votre réponse :**

> _______________________________________________________________

### Tenez-vous un inventaire de votre matériel et de vos logiciels ?
🔹 **Explication.** Différent d'un ordre de grandeur : une liste réellement tenue à jour, où l'on retrouve chaque machine et son responsable. On ne protège pas ce qu'on ne sait pas posséder.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Inventaire GLPI pour les serveurs ; postes suivis dans un tableur, incomplet_

✏️ **Votre réponse :**

> _______________________________________________________________

### Développez-vous des logiciels, et comment arrivent-ils en production ?
🔹 **Explication.** Si vous développez ou faites développer une application, décrivez le chemin d'une modification jusqu'à la production : qui valide, quels tests, quels contrôles de sécurité. Répondez « non » si vous n'utilisez que des logiciels du commerce.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Application interne, déploiement par l'éditeur après recette métier, sans test de sécurité_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels systèmes d'exploitation utilisez-vous ?
🔹 **Explication.** Les systèmes de vos postes et serveurs (Windows, Linux, macOS) et leurs versions si vous les connaissez. Des versions anciennes peuvent être vulnérables.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Windows 11 sur les postes, Windows Server 2019, quelques Linux_

✏️ **Votre réponse :**

> _______________________________________________________________

### Utilisez-vous encore des systèmes anciens / non maintenus ?
🔹 **Explication.** Des logiciels ou machines qui ne reçoivent plus de mises à jour de sécurité (ex. Windows 7, vieux équipements médicaux). Ils sont souvent les points faibles.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Deux échographes sous un ancien Windows non mis à jour_

✏️ **Votre réponse :**

> _______________________________________________________________


## 5. Hébergement et cloud

*Où vivent vos données et vos applications.*

### Comment est hébergé votre système d'information ?
🔹 **Explication.** « Sur site » = dans vos locaux ; « cloud » = chez un fournisseur sur Internet ; « hybride » = un mélange des deux.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : sur_site | cloud | hybride.
Exemple : _hybride_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels fournisseurs cloud et services en ligne utilisez-vous ?
🔹 **Explication.** Les grands services externes (Microsoft 365, Google, AWS, Azure) et applications en ligne (SaaS) que vous utilisez. Vos données y transitent ou y résident.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Microsoft 365, hébergeur HDS pour le SIH_

✏️ **Votre réponse :**

> _______________________________________________________________

### Où sont physiquement stockées vos données ?
🔹 **Explication.** Le ou les pays d'hébergement. Un stockage hors Union Européenne peut poser des questions réglementaires (RGPD).

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _France (hébergeur certifié HDS)_

✏️ **Votre réponse :**

> _______________________________________________________________

### Vos hébergeurs ont-ils des certifications de sécurité ?
🔹 **Explication.** Par exemple HDS (hébergeur de données de santé), ISO 27001, SecNumCloud. Ces labels attestent d'un niveau de sécurité de votre prestataire.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Hébergeur certifié HDS et ISO 27001_

✏️ **Votre réponse :**

> _______________________________________________________________


## 6. Réseau et accès distant

*Comment vos systèmes communiquent entre eux et avec l'extérieur.*

### Comment votre réseau est-il organisé ?
🔹 **Explication.** Décrivez simplement : un seul réseau à plat, ou des zones séparées (bureautique, serveurs, invités) ? La séparation limite la propagation d'une attaque.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Réseau segmenté : bureautique, serveurs, réseau médical isolé_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels services sont accessibles depuis Internet ?
🔹 **Explication.** Ce qui est visible de l'extérieur (site web, portail, messagerie, accès distant). Tout ce qui est exposé peut être attaqué.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Portail patient, webmail, VPN_

✏️ **Votre réponse :**

> _______________________________________________________________

### Qui travaille à distance, et depuis quel matériel ?
🔹 **Explication.** Quels profils se connectent depuis l'extérieur (domicile, déplacement), et depuis un poste fourni par l'entreprise ou leur propre matériel. Répondez « non » si personne ne travaille à distance.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte.
Exemple : _Administratifs et médecins, depuis des portables fournis par l'établissement_

✏️ **Votre réponse :**

> _______________________________________________________________

### Par quels moyens accède-t-on à distance au système ?
🔹 **Explication.** VPN = tunnel sécurisé ; MFA = double authentification (mot de passe + code) ; VDI = bureau virtuel. Ces moyens protègent les connexions à distance.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _VPN avec MFA pour les administratifs, VPN simple pour les médecins_

✏️ **Votre réponse :**

> _______________________________________________________________

### Disposez-vous de réseaux Wi-Fi, et sont-ils séparés (invités / interne) ?
🔹 **Explication.** Un Wi-Fi invité ouvert mais isolé du réseau interne évite qu'un visiteur atteigne vos systèmes sensibles.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Wi-Fi interne protégé + Wi-Fi invité isolé_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous des connexions permanentes avec des partenaires ?
🔹 **Explication.** Des liaisons directes avec des prestataires ou partenaires (télémaintenance, échanges de données). Elles étendent votre surface d'exposition.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Liaison de télémaintenance avec l'éditeur du SIH_

✏️ **Votre réponse :**

> _______________________________________________________________


## 7. Identités et gestion des accès

*Comment vous contrôlez qui accède à quoi.*

### Comment gérez-vous les comptes utilisateurs ?
🔹 **Explication.** Avez-vous un annuaire central (ex. Active Directory) ? Comment sont créés, modifiés et surtout supprimés les comptes quand une personne part ?

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Active Directory ; création/suppression via un processus RH_

✏️ **Votre réponse :**

> _______________________________________________________________

### Qui vérifie, et à quelle fréquence, que chacun n'a que les accès nécessaires ?
🔹 **Explication.** Les droits s'accumulent au fil des changements de poste et ne sont presque jamais retirés. Une revue périodique compare les accès réels aux besoins réels. Précisez la date de la dernière revue.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Aucune revue formelle ; les droits suivent les demandes des managers_

✏️ **Votre réponse :**

> _______________________________________________________________

### L'authentification multifacteur (MFA) est-elle en place ?
🔹 **Explication.** La MFA demande une seconde preuve en plus du mot de passe (code sur téléphone, appli, clé). Précisez où elle s'applique (messagerie, VPN, applications sensibles).

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte.
Exemple : _MFA sur la messagerie et le VPN administratif, pas encore sur le SIH_

✏️ **Votre réponse :**

> _______________________________________________________________

### Comment sont gérés les comptes à privilèges (administrateurs) ?
🔹 **Explication.** Les comptes « administrateur » ont tous les pouvoirs et sont la cible n°1 des attaquants. Sont-ils limités, nominatifs, surveillés ?

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Comptes admin nominatifs, mais pas de coffre-fort de mots de passe_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quelle est votre politique de mots de passe ?
🔹 **Explication.** Les règles imposées (longueur, complexité, renouvellement). Des mots de passe faibles sont facilement devinés.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _12 caractères minimum, pas de renouvellement forcé_

✏️ **Votre réponse :**

> _______________________________________________________________


## 8. Postes de travail et serveurs

*La protection des ordinateurs et serveurs eux-mêmes.*

### Quel antivirus / EDR est déployé ?
🔹 **Explication.** Un antivirus détecte les logiciels malveillants ; un EDR (détection et réponse) est un antivirus avancé qui repère aussi les comportements suspects. Précisez le produit.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Microsoft Defender for Endpoint sur tous les postes_

✏️ **Votre réponse :**

> _______________________________________________________________

### Comment appliquez-vous les mises à jour de sécurité (correctifs) ?
🔹 **Explication.** Les éditeurs publient régulièrement des correctifs qui bouchent des failles. Sont-ils appliqués automatiquement, rapidement, ou de façon irrégulière ?

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Mises à jour automatiques sur les postes, plus lentes sur les serveurs_

✏️ **Votre réponse :**

> _______________________________________________________________

### Qui est administrateur de son propre poste, et pourquoi ?
🔹 **Explication.** Si un utilisateur est « administrateur » de sa machine, un logiciel malveillant qu'il ouvre obtient aussi tous les droits. Indiquez quels profils le sont encore et ce qui le justifie.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Personne, sauf 4 développeurs et les techniciens support_

✏️ **Votre réponse :**

> _______________________________________________________________

### Comment sont gérés les smartphones et tablettes fournis par l'entreprise ?
🔹 **Explication.** Précisez s'ils sont administrés à distance (MDM), chiffrés, et si l'entreprise peut les effacer en cas de perte ou de vol.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Téléphones pro sous MDM, chiffrés, effacement à distance possible_

✏️ **Votre réponse :**

> _______________________________________________________________

### Des appareils personnels accèdent-ils aux données professionnelles ?
🔹 **Explication.** Le BYOD (appareil personnel utilisé pour le travail) élargit la surface à protéger sur du matériel que vous ne maîtrisez pas. Précisez ce qui est accessible depuis ces appareils.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Messagerie accessible depuis les téléphones personnels, sans MDM_

✏️ **Votre réponse :**

> _______________________________________________________________

### Comment repérez-vous les failles connues de vos systèmes ?
🔹 **Explication.** Distinct de l'application des correctifs : il s'agit de SAVOIR ce qui est vulnérable (scans réguliers, veille sur les alertes, tests d'intrusion). Sans découverte, on ne corrige que ce qui est déjà connu.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Scan de vulnérabilités mensuel sur les serveurs exposés ; veille CERT-FR ; rien sur les postes_

✏️ **Votre réponse :**

> _______________________________________________________________


## 9. Données personnelles (RGPD)

*Cette partie concerne les données relatives à des personnes (clients, patients, salariés). Le RGPD impose des obligations précises et prévoit des sanctions.*

### Sur quelles personnes détenez-vous des informations ?
🔹 **Explication.** Toute information se rapportant à une personne identifiable (nom, email, dossier, numéro) compte. Citez les groupes concernés — clients, patients, salariés, candidats. Répondez « aucune » si vous n'en traitez réellement pas.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _Patients, salariés, candidats à l'embauche_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quelles catégories de données personnelles ?
🔹 **Explication.** Précisez les types (clients, salariés, prospects) et surtout les données « sensibles » (santé, biométrie, opinions), plus strictement encadrées par la loi.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Patients (données de santé), salariés, prospects_

✏️ **Votre réponse :**

> _______________________________________________________________

### Combien de personnes concernées environ ?
🔹 **Explication.** Un ordre de grandeur du nombre d'individus dont vous détenez les données. Un volume important augmente l'impact d'une fuite.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Nombre.
Exemple : _~50 000 patients_

✏️ **Votre réponse :**

> _______________________________________________________________

### Des données sont-elles transférées hors Union Européenne ?
🔹 **Explication.** Par exemple via un prestataire américain. Ces transferts nécessitent des garanties juridiques particulières sous le RGPD.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Oui / Non + détails.
Exemple : _Oui, support d'un éditeur hébergé aux États-Unis_

✏️ **Votre réponse :**

> _______________________________________________________________

### Tenez-vous un registre des activités de traitement ?
🔹 **Explication.** Le registre liste vos usages de données personnelles : quelles données, pour quelle finalité, conservées combien de temps, partagées avec qui. Précisez s'il est à jour et qui le tient.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Registre tenu et revu chaque année par le DPO externe_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous désigné un délégué à la protection des données (DPO) ?
🔹 **Explication.** Le DPO est le référent RGPD. Précisez s'il est interne ou externe, et s'il a été déclaré à la CNIL — l'obligation dépend de votre activité et du type de données traitées.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _DPO externe mutualisé, déclaré à la CNIL_

✏️ **Votre réponse :**

> _______________________________________________________________

### Combien de temps conservez-vous les données, et comment sont-elles supprimées ?
🔹 **Explication.** Une donnée gardée au-delà de son utilité est un risque sans contrepartie. Indiquez les durées de conservation prévues et ce qui déclenche réellement une suppression (automatique, manuelle, jamais).

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Dossiers patients conservés 20 ans ; purge des logs à 6 mois ; pas de purge automatisée sur les sauvegardes_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels sous-traitants accèdent à des données personnelles ?
🔹 **Explication.** Les prestataires qui manipulent vos données pour vous (hébergeur, éditeur SaaS, infogérance). Vous restez responsable de ce qu'ils en font.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste.
Exemple : _Hébergeur HDS, éditeur du SIH, prestataire de paie_

✏️ **Votre réponse :**

> _______________________________________________________________

### Vos données sensibles sont-elles chiffrées ?
🔹 **Explication.** Le chiffrement rend les données illisibles sans la clé. Précisez « au repos » (sur les disques/sauvegardes) et « en transit » (pendant les échanges réseau).

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Chiffrement des sauvegardes et des échanges web ; disques serveurs non chiffrés_

✏️ **Votre réponse :**

> _______________________________________________________________


## 10. Sauvegarde et continuité d'activité

*Votre capacité à résister à une panne, une destruction ou un rançongiciel.*

### Quelle est votre stratégie de sauvegarde ?
🔹 **Explication.** À quelle fréquence sauvegardez-vous ? Existe-t-il une copie « hors ligne » ou « immuable » (que même un attaquant ne peut effacer) ? C'est la dernière défense contre un rançongiciel.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Texte.
Exemple : _Sauvegarde quotidienne, avec une copie hors ligne hebdomadaire_

✏️ **Votre réponse :**

> _______________________________________________________________

### Testez-vous régulièrement la restauration des sauvegardes ?
🔹 **Explication.** Une sauvegarde jamais testée peut se révéler illisible le jour où on en a besoin. Indiquez si et à quelle fréquence vous vérifiez qu'elle fonctionne.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Test de restauration semestriel_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous un plan de reprise informatique (PRA) ?
🔹 **Explication.** Comment le système d'information est techniquement remonté après un sinistre majeur (incendie, rançongiciel) : où, à partir de quoi, par qui. Précisez la date du dernier test réel.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _PRA documenté, bascule testée en octobre dernier_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous un plan de continuité métier (PCA) ?
🔹 **Explication.** Comment l'activité continue PENDANT la panne, sans l'informatique : procédures dégradées, papier, report vers un autre site. C'est distinct du redémarrage technique.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Procédure papier pour les admissions ; PCA métier en cours de rédaction_

✏️ **Votre réponse :**

> _______________________________________________________________

### Combien de temps pouvez-vous rester à l'arrêt, et quelle perte de données tolérez-vous ?
🔹 **Explication.** En clair : au bout de combien de temps l'arrêt devient-il critique (RTO), et jusqu'à combien d'heures de données pouvez-vous perdre (RPO) ? Une estimation suffit.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Arrêt tolérable ~4h, perte de données max ~1h_

✏️ **Votre réponse :**

> _______________________________________________________________


## 11. Journalisation, détection et incidents

*Votre capacité à voir ce qui se passe et à réagir.*

### Conservez-vous des journaux (logs) des activités système ?
🔹 **Explication.** Les journaux enregistrent les connexions et actions. Ils sont indispensables pour comprendre une attaque après coup. Précisez leur durée de conservation.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Journaux conservés 6 mois sur les serveurs principaux_

✏️ **Votre réponse :**

> _______________________________________________________________

### Surveillez-vous activement les alertes de sécurité (SIEM/SOC) ?
🔹 **Explication.** Un SIEM centralise les alertes ; un SOC est l'équipe qui les surveille en continu. Beaucoup d'organisations n'en ont pas — dites simplement l'état réel.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Pas de SOC ; alertes Defender consultées ponctuellement_

✏️ **Votre réponse :**

> _______________________________________________________________

### Avez-vous déjà subi des incidents de sécurité notables ?
🔹 **Explication.** Virus, rançongiciel, fuite de données, intrusion, fraude… Même anciens, ils renseignent sur votre exposition. Aucune honte : l'objectif est d'apprendre.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Une tentative de rançongiciel bloquée en 2023_

✏️ **Votre réponse :**

> _______________________________________________________________

### Disposez-vous d'une procédure de réponse aux incidents ?
🔹 **Explication.** Qui appeler, quoi faire, dans quel ordre en cas de crise cyber. Et avez-vous un contact d'assistance (prestataire, assurance cyber, CERT) ?

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Procédure informelle ; contrat d'assistance avec un prestataire_

✏️ **Votre réponse :**

> _______________________________________________________________

### En cas de violation de données, qui devez-vous prévenir et sous quel délai ?
🔹 **Explication.** Certaines obligations imposent un délai court et non négociable — par exemple 72 heures vers l'autorité de contrôle, plus l'information des personnes concernées si le risque est élevé. Indiquez si ces destinataires et ces délais sont écrits, et qui décide.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _CNIL sous 72h et patients concernés ; décidé par le DPO, procédure non écrite_

✏️ **Votre réponse :**

> _______________________________________________________________


## 12. Écosystème et tiers de confiance

*Vos dépendances envers d'autres organisations — souvent une porte d'entrée des attaques.*

### Quels sont vos fournisseurs / prestataires critiques ?
🔹 **Explication.** Ceux dont une panne ou un piratage vous impacterait directement (hébergeur, éditeur, infogérant, fournisseur d'énergie). L'attaque passe souvent par eux.

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _Hébergeur HDS, éditeur du SIH, prestataire d'infogérance_

✏️ **Votre réponse :**

> _______________________________________________________________

### Une partie de votre informatique est-elle infogérée / externalisée ?
🔹 **Explication.** Confiez-vous la gestion de vos systèmes à un prestataire externe ? Si oui, il a des accès étendus qu'il faut encadrer.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Infogérance partielle des serveurs par un prestataire local_

✏️ **Votre réponse :**

> _______________________________________________________________

### Vos contrats prestataires incluent-ils des exigences de sécurité ?
🔹 **Explication.** Des engagements écrits (confidentialité, notification en cas d'incident, droit d'audit). Sans clause, vous avez peu de recours.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Clauses RGPD présentes, exigences de sécurité limitées_

✏️ **Votre réponse :**

> _______________________________________________________________


## 13. Sécurité physique et facteur humain

*Les locaux et les personnes comptent autant que la technique.*

### Comment sont protégés vos locaux et salles serveurs ?
🔹 **Explication.** Contrôle d'accès (badges), vidéosurveillance, salle informatique fermée, protection contre l'incendie et les coupures électriques.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Badges, salle serveurs fermée à clé, onduleurs_

✏️ **Votre réponse :**

> _______________________________________________________________

### Vos collaborateurs sont-ils sensibilisés à la cybersécurité ?
🔹 **Explication.** Formations, campagnes de faux e-mails piégés (phishing), charte informatique. L'humain est la cible la plus fréquente des attaques.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Sensibilisation annuelle, pas de test de phishing_

✏️ **Votre réponse :**

> _______________________________________________________________

### Existe-t-il une charte informatique et des politiques de sécurité écrites ?
🔹 **Explication.** Des documents qui fixent les règles d'usage et de sécurité, connus des employés.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Oui / Non + détails.
Exemple : _Charte signée à l'embauche ; PSSI en cours de rédaction_

✏️ **Votre réponse :**

> _______________________________________________________________


## 14. Conformité, référentiels et historique

*Les cadres réglementaires et normatifs qui s'appliquent, et ce qui a déjà été fait.*

### Quels référentiels / réglementations s'appliquent à vous ?
🔹 **Explication.** Les cadres de sécurité et lois applicables. Pré-remplis : ISO 27001, guide d'hygiène ANSSI, RGPD, NIST. Confirmez, retirez, ou ajoutez (ex. HDS, HIPAA, PCI-DSS, NIS2).

🔸 *Priorité : Critique — indispensable pour démarrer l'étude.*
Format attendu : Liste.
Exemple : _ISO27001, ANSSI_hygiene, RGPD, NIST, HDS_

✏️ **Votre réponse :**

> _______________________________________________________________

### Détenez-vous déjà des certifications ou labels de sécurité ?
🔹 **Explication.** Par exemple ISO 27001, HDS, SecNumCloud. Précisez leur périmètre et leur validité.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Certification HDS de l'hébergeur ; pas de certification propre_

✏️ **Votre réponse :**

> _______________________________________________________________

### Des audits, tests d'intrusion ou évaluations ont-ils déjà eu lieu ?
🔹 **Explication.** Tout travail antérieur (audit ANSSI, pentest, évaluation interne) et ses grandes conclusions. Cela évite de repartir de zéro.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Texte.
Exemple : _Audit de maturité ANSSI en 2023, quelques écarts identifiés_

✏️ **Votre réponse :**

> _______________________________________________________________

### Quels documents joignez-vous à ce questionnaire ? (facultatif)
🔹 **Explication.** Tout document utile : politique de sécurité, schéma réseau, inventaire, rapport d'audit précédent, registre RGPD. C'est facultatif mais très utile — l'agent les lira et en extraira les informations, en citant ses sources.

🔸 *Priorité : Important — si vous ne pouvez pas répondre, indiquez pourquoi.*
Format attendu : Liste de fichiers.
Exemple : _PSSI.pdf, schema_reseau.pdf, rapport_audit_2023.pdf_

✏️ **Votre réponse :**

> _______________________________________________________________

