# Socle d’infrastructure — Membre A

Ce dossier est l’espace de travail du membre A : infrastructure, identité et sécurité. Il rend le jalon 1 traçable sans prétendre qu’un service est déjà opérationnel.

## Statut au 1er novembre 2026

- [x] Dépôt Git local, licence AGPL-3.0 et documentation de cadrage.
- [x] Choix du nom public : **Oryma**.
- [x] Contrat d’environnement : `.env.example` sans secret réel.
- [ ] Adresse de démonstration unique (`ORYMA_HOST`) choisie et testée sur les deux appareils.
- [ ] Compose : PostgreSQL, Caddy, Synapse, Element, Keycloak et API d’administration.
- [ ] Royaume Keycloak, rôles `admin` / `agent`, TOTP obligatoire.
- [ ] OIDC Synapse–Keycloak, inscription Matrix et accès invité désactivés.
- [ ] Test de révocation à deux appareils et note de sécurité mise à jour.

## Ordre de démarrage conseillé

1. Vérifier que Docker Compose démarre un conteneur minimal et que les volumes sont ignorés par Git.
2. Fixer `ORYMA_HOST` après avoir vérifié sa résolution sur le téléphone. Ne pas le modifier après l’initialisation de Synapse.
3. Monter PostgreSQL puis Synapse avec une salle chiffrée de test.
4. Ajouter Caddy et Element Web sur la même adresse HTTPS.
5. Ajouter Keycloak, le TOTP puis l’OIDC ; valider l’intrus avant d’intégrer l’API de révocation.

## Règles non négociables

- Aucun secret réel, certificat privé ou volume Docker dans Git.
- Aucun port interne publié : seul Caddy devient accessible depuis le réseau local.
- Aucun chiffrement écrit par l’équipe : Element et Matrix fournissent Olm/Megolm.
- Toute commande présentée dans le README doit avoir été réellement exécutée et vérifiée.

Les critères complets restent dans le [guide de développement](../docs/development/README.md) et le [guide de déploiement](../docs/deployment/README.md).
