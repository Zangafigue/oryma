# msgsov — Cahier des charges

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>PROJECT_OVERVIEW.md</code></p>

## 1. Contexte

Les agents publics échangent des informations de service, parfois sensibles, sur des messageries grand public dont les serveurs et les règles échappent à l’État. Le Burkina Faso a besoin d’une messagerie instantanée souveraine, aussi simple que les applications du marché, mais conçue pour la sécurité des échanges administratifs.

## 2. Objectifs

1. Fournir une messagerie instantanée (messages, groupes, fichiers) pour les agents de l’administration.
2. Garantir que le serveur ne peut lire aucun message ni fichier (chiffrement de bout en bout).
3. Permettre à l’État d’héberger l’ensemble sur sa propre infrastructure, en une seule commande.
4. Maîtriser les accès : enrôlement préalable, second facteur, rôles, révocation immédiate.
5. Démontrer une fonctionnalité innovante adaptée au contexte burkinabè : salles classifiées avec expiration.
6. Fonctionner sur ordinateur et sur téléphone.

## 3. Périmètre

| Inclus | Exclu |
|---|---|
| Messages 1-à-1 et groupes, envoi de fichiers | Appels audio et vidéo |
| Enrôlement par un administrateur, TOTP, rôles | Fédération avec d’autres serveurs Matrix |
| Révocation sur tous les appareils | Applications natives Android et iOS |
| Classification et expiration des salles (messages inclus) | Archivage légal (piste d’évolution) |
| Journal d’audit des actions d’administration | Montée en charge : répartition de charge, workers (piste d’évolution) |
| Client web utilisable sur PC et téléphone | Effacement à distance de l’appareil |
| Interface en langue nationale (bonus) | Annuaire et WebAuthn (coupés) |

## 4. Contraintes

| Type | Contrainte |
|---|---|
| Réglementaire (sujet) | Tout en open source, licence reconnue par l’OSI, fichier LICENSE à la racine |
| Sécurité (sujet) | Aucune cryptographie développée par l’équipe, aucun message en clair côté serveur (éliminatoire) |
| Technique (sujet) | Aucun service tiers indispensable, installation en une commande |
| Données | Uniquement des données et comptes fictifs |
| Éthique | Aucun test d’intrusion sur un système réel (disqualification) |
| Délai | Dépôt au plus tard le 1er novembre 2026 ; heure limite à confirmer auprès du point focal du MTDPCE |
| Équipe | 2 à 3 étudiants de la même université ; l’équipe compte deux membres |

## 5. Livrables

1. Fiche équipe (avec attestations d’inscription 2026-2027).
2. Note de pré-projet (2 pages maximum).
3. Note de sécurité (2 pages maximum), construite à partir de [securite.md](../securite.md).
4. Dépôt Git public : README.md en français (2 pages maximum), LICENSE, code serveur et client, fichiers de déploiement, comptes de démonstration fictifs, historique de commits progressifs.
5. Vidéo de démonstration (3 minutes maximum).

## 6. Critères d’acceptation

| Épreuve du jury | Critère de réussite |
|---|---|
| Le serveur ne lit rien | Un export de la base et une capture réseau ne montrent aucun message ni fichier en clair |
| Révocation | Un agent révoqué en pleine conversation perd immédiatement l’accès, y compris aux nouveaux messages |
| Intrus | Un compte non enrôlé est rejeté à la connexion et à l’entrée dans un groupe |
| Innovation | La classification et l’expiration sont démontrées de bout en bout |
| Explication du code | Chaque membre sait expliquer l’enrôlement, la révocation et le lien Keycloak–Synapse |

## 7. Planning

Le détail des blocs, des durées et de la répartition entre les deux membres est dans le [guide de développement](../development/README.md).
