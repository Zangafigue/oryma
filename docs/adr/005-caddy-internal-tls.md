# ADR-005 — Caddy avec certificat interne comme proxy inverse

## Statut

Accepté

## Date

2026-11-01

## Contexte

Aucun service tiers ne doit être nécessaire au fonctionnement : un certificat Let’s Encrypt dépend d’un service externe. Le trafic doit rester chiffré entre navigateur et serveur.

## Décision

Utiliser **Caddy** en proxy inverse unique avec TLS interne (`tls internal`). Seul Caddy publie un port. Les journaux d’accès sont désactivés ou sans adresse IP.

## Alternatives considérées

### Nginx ou Traefik

- Avantages : très répandus.
- Inconvénients : configuration plus longue pour un certificat interne.
- Motif du rejet : Caddy est plus court à configurer.

### Let’s Encrypt

- Avantages : certificat reconnu partout.
- Inconvénients : service externe, contraire à la souveraineté.
- Motif du rejet : écartée.

## Conséquences

### Positives

- Certificat interne en quelques lignes, aucune dépendance externe.
- Un point d’entrée unique facilite le durcissement et les en-têtes de sécurité.

### Contraintes et risques

- Le certificat n’est pas reconnu par défaut par les téléphones : installer l’autorité racine de Caddy sur chaque appareil de démonstration ([guide de déploiement](../deployment/README.md)).
- La clé privée de l’autorité ne quitte jamais le serveur et n’entre jamais dans le dépôt.
- Détruire le volume de Caddy régénère l’autorité : les appareils doivent la réinstaller.

## Références

- INV-07, INV-08, INV-09.
- `docs/deployment/README.md`.
