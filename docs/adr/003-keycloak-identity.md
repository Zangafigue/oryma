# ADR-003 — Keycloak pour l’identité, le second facteur et les rôles

## Statut

Accepté

## Date

2026-11-01

## Contexte

Synapse n’offre pas de second facteur natif. Le sujet exige des agents préalablement enrôlés, une authentification forte et des rôles. Une authentification écrite par l’équipe serait du code de sécurité à expliquer ligne par ligne au jury.

## Décision

Utiliser **Keycloak** comme fournisseur d’identité OIDC pour Synapse et pour la console d’administration : TOTP obligatoire, rôles `admin` et `agent`, comptes créés uniquement par enrôlement. Le mot de passe local de Synapse est désactivé.

## Alternatives considérées

### Authelia

- Avantages : très léger, TOTP et WebAuthn, configuration en fichier.
- Inconvénients : pas de console de gestion des comptes ; révocation en direct moins fluide.
- Motif du rejet : la démonstration de révocation devant le jury est plus fragile.

### Matrix Authentication Service

- Avantages : conçu pour l’écosystème Matrix.
- Inconvénients : plus récent, documentation moindre, support du second facteur à vérifier.
- Motif du rejet : trop d’inconnues pour le délai.

### Authentification écrite par l’équipe

- Avantages : légère en apparence.
- Inconvénients : code de sécurité risqué, à défendre ligne par ligne, risque d’élimination.
- Motif du rejet : écartée.

## Conséquences

### Positives

- Console et API d’administration pour désactiver un agent en un appel.
- TOTP, rôles, blocage anti-force brute et durées de session intégrés.
- WebAuthn possible plus tard sans refonte.

### Contraintes et risques

- Keycloak consomme beaucoup de mémoire : au moins 2 Go de RAM, 4 Go recommandés.
- Un administrateur Keycloak pourrait ouvrir une session à la place d’un agent depuis un nouvel appareil : menace à documenter, parades dans la note de sécurité (vérification des appareils, journal d’audit).
- La liaison OIDC Synapse–Keycloak est le risque de planning principal : royaume préconfiguré en fichier et test précoce.

## Références

- INV-03, INV-04, INV-05.
- `docs/api/specification.md`.
