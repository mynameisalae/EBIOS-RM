# Questionnaire de contexte rempli — Clinique du Val Fleuri

## 1. Identité et gouvernance
- Nom de l'organisation : Clinique du Val Fleuri
- Forme juridique : SAS privée, filiale d'un groupe de santé régional
- Secteur d'activité : Santé — établissement de soins privé
- Activité : Prise en charge médicale de patients en hospitalisation et consultations externes.
- Effectif total : beaucoup de monde, difficile à dire
- Périmètre géographique : France (site principal de Lyon)
- Responsable sécurité : Un RSSI à temps partiel et un DPO externe mutualisé.
- Maturité cybersécurité : En cours de structuration.

## 2. Périmètre et objectifs
- Objectifs de l'audit : Se mettre en conformité HDS et réduire le risque de fuite de données patients.
- Dans le périmètre : SIH, imagerie médicale (PACS), messagerie, accès distant des médecins.
- Hors périmètre : La billetterie de la cafétéria (aucune donnée sensible).
- Commanditaires : La Direction Générale et le Directeur des Systèmes d'Information.

## 3. Contexte métier
- Processus critiques : Prise en charge des patients, gestion du dossier médical, imagerie médicale.
- Informations sensibles : Dossiers médicaux, résultats d'examens, données RH.
- Impact d'un arrêt : Report de soins, risque pour la sécurité des patients, pertes financières, atteinte à la réputation.

## 4. Système d'information
- Résumé du SI : SIH central hébergé chez un prestataire HDS, messagerie Microsoft 365, imagerie PACS, postes sous Windows.
- Applications principales : SIH (éditeur externe), PACS imagerie, logiciel de paie en SaaS.
- Parc : environ 30 serveurs et 350 postes.
- Systèmes obsolètes : Deux échographes fonctionnent sous un ancien Windows qui n'est plus mis à jour.

## 5. Hébergement
- Hébergement : hybride
- Fournisseurs cloud : Microsoft 365, hébergeur HDS pour le SIH.
- Localisation des données : France (hébergeur certifié HDS).

## 6. Réseau et accès distant
- Télétravail autorisé : Oui, pour les fonctions administratives et les médecins.
- Accès distant : VPN avec double authentification pour les administratifs, VPN simple pour les médecins.

## 7. Identités et accès
- Authentification forte (MFA) : MFA sur la messagerie et le VPN administratif, mais pas encore sur le SIH.

## 8. Postes de travail
- Antivirus / EDR : (non renseigné)
- Droits administrateur : Non, sauf quelques exceptions techniques.

## 9. Données personnelles (RGPD)
- Traitement de données personnelles : Oui
- Catégories : Patients (données de santé), salariés, prospects.
- Nombre de personnes concernées : environ 50 000 patients.
- Sous-traitants : Hébergeur HDS, éditeur du SIH, prestataire de paie.

## 10. Sauvegarde et continuité
- Stratégie de sauvegarde : (non renseigné)

## 11. Détection et incidents
- Incidents passés : Une tentative de rançongiciel bloquée en 2023.

## 12. Écosystème
- Fournisseurs critiques : Hébergeur HDS, éditeur du SIH, prestataire d'infogérance.

## 14. Conformité
- Référentiels applicables : ANSSI_hygiene, RGPD, NIST, HDS
- Audits antérieurs : Audit de maturité ANSSI en 2023, quelques écarts identifiés.
