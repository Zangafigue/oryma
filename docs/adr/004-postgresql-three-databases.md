# ADR-004 — PostgreSQL 16 avec trois bases

## Statut

Accepté

## Date

2026-11-01

## Contexte

Synapse recommande PostgreSQL en usage réel, Keycloak a besoin d’une base, et le service d’administration doit conserver agents, salles et audit.

## Décision

Utiliser **PostgreSQL 16** dans un seul conteneur avec trois bases isolées : `synapse`, `keycloak` et `adminapi`, chacune avec son propre compte. La base de Synapse est créée avec les paramètres de classement et de jeu de caractères exigés par Synapse.

## Alternatives considérées

### SQLite

- Avantages : aucune installation.
- Inconvénients : déconseillé pour Synapse en usage réel.
- Motif du rejet : écartée.

### Plusieurs conteneurs PostgreSQL

- Avantages : isolation plus forte.
- Inconvénients : plus de mémoire et de configuration.
- Motif du rejet : disproportionné pour le prototype.

## Conséquences

### Positives

- Une seule base à sauvegarder et à surveiller.
- Comptes distincts : le service d’administration ne peut pas lire les tables de Synapse.
- Le compte du journal d’audit est limité à l’ajout et à la lecture.

### Contraintes et risques

- Un incident sur le conteneur touche les trois bases.
- Les migrations SQL de `adminapi` sont gérées par l’équipe et numérotées.

## Références

- INV-10.
- `docs/data/data-dictionary.md`.
