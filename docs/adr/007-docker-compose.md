# ADR-007 — Docker Compose pour l’installation en une commande

## Statut

Accepté

## Date

2026-11-01

## Contexte

Le sujet exige une installation sur une infrastructure maîtrisée, sans service tiers, en une seule commande (Docker Compose ou équivalent).

## Décision

Fournir un `docker-compose.yml` avec six services, un réseau externe réservé à Caddy et un réseau interne sans accès sortant pour les autres, des volumes nommés, des `healthcheck`, `restart: unless-stopped` et des versions d’images figées.

## Alternatives considérées

### Installation manuelle

- Avantages : contrôle fin.
- Inconvénients : non reproductible, longue.
- Motif du rejet : écartée.

### Kubernetes

- Avantages : adapté à la production.
- Inconvénients : disproportionné pour un prototype.
- Motif du rejet : écartée.

## Conséquences

### Positives

- Installation reproductible sur une machine propre.
- Isolation réseau simple.
- Cité en exemple par le sujet.

### Contraintes et risques

- Les versions d’images ne sont pas figées de mémoire : au bloc 1, dernière version stable publiée depuis plus de deux semaines, licence vérifiée et notée dans le README.
- Le test d’installation de zéro (`down -v` puis `up`) régénère l’autorité de Caddy : le faire avant d’installer le certificat sur le téléphone.

## Références

- INV-07, INV-08.
- `docs/deployment/README.md`.
