# ADR-009 — Client web installable plutôt qu’applications natives

## Statut

Accepté

## Date

2026-11-01

## Contexte

L’application doit fonctionner sur ordinateur et téléphone avec le même compte et la même adresse. Les applications natives demandent un certificat reconnu et des prérequis de connexion supplémentaires, et les notifications en arrière-plan passent par un service tiers.

## Décision

Utiliser **Element Web adapté aux petits écrans**, installable sur l’écran d’accueil (PWA). Les applications natives ne sont pas ciblées. La console d’administration est utilisable sur téléphone.

## Alternatives considérées

### Applications natives Element (Android, iOS)

- Avantages : expérience native, notifications.
- Inconvénients : certificat reconnu nécessaire ; sous Android les autorités ajoutées par l’utilisateur sont souvent refusées par les applications ; prérequis de connexion.
- Motif du rejet : hors périmètre du prototype.

### Application mobile écrite par l’équipe

- Avantages : contrôle total.
- Inconvénients : hors délai.
- Motif du rejet : écartée.

## Conséquences

### Positives

- Un seul client pour PC et téléphone.
- Aucune publication sur une boutique d’applications.

### Contraintes et risques

- Pas de notification en arrière-plan garantie (limite écrite dans le README).
- Le téléphone doit faire confiance à l’autorité racine de Caddy.
- Le comportement exact de l’invite « installer l’application mobile » d’Element est à vérifier dans la version utilisée.

## Références

- FR-050, NFR-U01.
- `docs/deployment/README.md`.
