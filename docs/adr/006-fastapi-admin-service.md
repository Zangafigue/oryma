# ADR-006 — FastAPI pour le service d’administration

## Statut

Accepté

## Date

2026-11-01

## Contexte

Il faut un petit service qui enrôle, révoque, crée les salles classifiées, tient l’annuaire et l’audit en appelant les API de Keycloak et de Synapse. C’est la seule partie réellement écrite par l’équipe.

## Décision

Utiliser **Python et FastAPI**, avec validation de données, documentation OpenAPI générée, tests pytest. Les routes valident le jeton Keycloak (signature, émetteur, audience, expiration) et le rôle dans une dépendance commune.

## Alternatives considérées

### Django

- Avantages : administration intégrée.
- Inconvénients : cadre plus large que nécessaire.
- Motif du rejet : FastAPI suffit pour une petite API.

### Flask

- Avantages : simple.
- Inconvénients : validation et documentation à assembler.
- Motif du rejet : moins de fonctions prêtes à l’emploi.

### Node.js

- Avantages : langage commun avec le web.
- Inconvénients : moins d’unité avec les outils de test choisis.
- Motif du rejet : pas d’avantage décisif.

## Conséquences

### Positives

- Écriture rapide, contrats d’entrée et de sortie validés, OpenAPI générée.
- Bon outil pour des appels vers Keycloak et Synapse.
- Peu de code à expliquer.

### Contraintes et risques

- Le jeton d’administration de Synapse est très puissant : jamais exposé, rôle vérifié sur chaque appel.
- Deux comptes de service Synapse distincts (administration et création de salles) pour limiter les droits.
- Le typage n’est pas garanti par les annotations seules : contrôle en lint.

## Références

- INV-05, INV-06, INV-10.
- `docs/api/specification.md`.
