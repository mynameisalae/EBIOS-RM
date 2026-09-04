# Questionnaire de contexte rempli — Mondial-Tickets

## 1. Identité et gouvernance
- Nom de l'organisation : Mondial-Tickets
- Forme juridique : Société de billetterie en ligne
- Secteur d'activité : Revente officielle de billets pour de grands événements sportifs internationaux
- Activité : Vente en ligne de billets d'événements sportifs (football, rugby) pour le compte de fédérations partenaires (FIFA, IRB/World Rugby, FFF)
- Effectif total : 50 collaborateurs (35 à Paris, 15 à Berlin)
- Périmètre géographique : France (siège, Paris) et Allemagne (filiale, Berlin)
- Responsable sécurité : Aucun RSSI ni DPO désigné à ce jour ; aucune politique de sécurité formalisée
- Maturité cybersécurité : Très faible — aucune démarche SMSI existante avant la présente mission

## 2. Périmètre et objectifs
- Objectifs de l'audit : Garantir la confidentialité, l'intégrité et la disponibilité des informations traitées ; répondre aux obligations RGPD ; sécuriser la relation de confiance avec les fédérations sportives et les ministères de l'Intérieur
- Dans le périmètre : Processus de vente en ligne de bout en bout (consultation, panier, contrôle anti-hooligan, paiement, génération et expédition des billets), serveurs de réservation, de paiement, base de données billetterie, serveur de sauvegarde
- Hors périmètre : Serveurs de comptabilité, de gestion du personnel et de messagerie, postes de travail, réseau interne, service d'éditique/courrier (non encore intégrés formellement au périmètre technique)
- Commanditaires : Direction Générale, Direction Informatique Paris, Responsable SMSI

## 3. Contexte métier
- Processus critiques : Vente en ligne de billets (consultation, affichage des prix, panier, contrôle anti-hooligan, paiement, validation, génération de billets, expédition)
- Informations sensibles : Données d'identité des spectateurs (nom, prénom, numéro de carte d'identité), données bancaires des clients, liste anti-hooligan confidentielle transmise par les ministères de l'Intérieur français et allemand
- Impact d'un arrêt : Arrêt total du service de vente en ligne lors des pics de charge (grands événements sportifs), perte de commission, perte de confiance des fédérations partenaires, risque de retrait des droits de revente

## 4. Système d'information
- Résumé du SI : Serveur WEB de réservation exposé sur Internet, serveur WEB de paiement connecté à la gestion comptable, base de données Billetterie centrale synchronisée entre Paris et Berlin, serveur de sauvegarde HP avec duplication entre les deux sites
- Applications principales : Site www.mondial-tickets.com (vente en ligne), système de contrôle anti-hooligan, système de paiement sécurisé avec autorisation bancaire en temps réel
- Parc : Quatre serveurs principaux identifiés (réservation, paiement, base de données billetterie, sauvegarde) répartis entre Paris et Berlin
- Systèmes obsolètes : (non renseigné)

## 5. Hébergement
- Hébergement : sur_site
- Fournisseurs cloud : Aucun identifié à ce stade
- Localisation des données : France (Paris, siège) et Allemagne (Berlin, filiale), synchronisation entre les deux sites

## 6. Réseau et accès distant
- Télétravail autorisé : Oui, encadré par VPN obligatoire pour les personnels itinérants
- Accès distant : VPN obligatoire ; aucun réseau Wi-Fi déployé sur les sites

## 7. Identités et accès
- Authentification forte (MFA) : Non déployée — aucune mesure de MFA identifiée sur le VPN ni sur les accès applicatifs

## 8. Postes de travail
- Antivirus / EDR : (non renseigné)
- Droits administrateur : Aucune séparation admin/courant identifiée, aucune politique de comptes nominatifs

## 9. Données personnelles (RGPD)
- Traitement de données personnelles : Oui
- Catégories : Données d'identité des spectateurs (nom, prénom, numéro de carte d'identité), données bancaires, liste anti-hooligan (donnée à caractère sensible transmise par une autorité publique)
- Nombre de personnes concernées : Volume important, non chiffré précisément (clients acheteurs de billets sur l'ensemble du portefeuille d'événements)
- Sous-traitants : Partenaire bancaire (autorisation de paiement en temps réel), correspondants des ministères de l'Intérieur (France et Allemagne)

## 10. Sauvegarde et continuité
- Stratégie de sauvegarde : Sauvegarde automatisée hebdomadaire (serveur de sauvegarde HP), avec duplication entre les sites de Paris et de Berlin ; aucun contrôle d'intégrité des sauvegardes ni RTO/RPO définis

## 11. Détection et incidents
- Incidents passés : Lors de la Coupe du Monde de rugby 2011 en Nouvelle-Zélande, des défaillances de fiabilité sur la plateforme de vente en ligne ont été constatées en pic de charge — événement déclencheur de la démarche de mise en sécurité

## 12. Écosystème
- Fournisseurs critiques : Fédérations sportives partenaires (FIFA, IRB/World Rugby, FFF), partenaire bancaire, ministères de l'Intérieur français et allemand (contrôle anti-hooligan)

## 14. Conformité
- Référentiels applicables : ANSSI_hygiene, RGPD, NIST
- Audits antérieurs : Aucun audit de sécurité formalisé mené à ce jour ; la présente mission constitue le premier cadrage EBIOS RM
