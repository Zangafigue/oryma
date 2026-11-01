# ADR-010 — Dépôt sous licence AGPL-3.0

## Statut

Accepté

## Date

2026-11-01

## Contexte

Le sujet impose une licence reconnue par l’Open Source Initiative avec un fichier LICENSE à la racine du dépôt.

## Décision

Publier le dépôt sous **AGPL-3.0**, cohérente avec Synapse et Element Web, également sous AGPL-3.0 (licences à vérifier sur les dépôts officiels).

## Alternatives considérées

### MIT ou Apache-2.0

- Avantages : très permissives.
- Inconvénients : moins cohérentes avec les composants AGPL assemblés.
- Motif du rejet : AGPL plus simple à justifier.

## Conséquences

### Positives

- Cohérence avec les composants principaux.
- Respect de l’obligation du sujet.

### Contraintes et risques

- Les licences et liens de chaque technologie doivent figurer dans le README.
- Toute modification d’un composant AGPL déployé doit rester publiable.

## Références

- `LICENSE`, `README.md`.
