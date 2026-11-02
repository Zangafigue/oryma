# Socle d’infrastructure — Membre A

Ce dossier est l’espace de travail du membre A : infrastructure, identité et sécurité. Il rend le jalon 1 traçable sans prétendre qu’un service est déjà opérationnel.

## Statut au 2 novembre 2026

- [x] Dépôt Git local, licence AGPL-3.0 et documentation de cadrage.
- [x] Choix du nom public : **Oryma**.
- [x] Contrat d’environnement : `.env.example` sans secret réel.
- [ ] Adresse de démonstration unique (`ORYMA_HOST`) choisie et testée sur les deux appareils.
- [x] Compose : PostgreSQL, Caddy, Synapse, Element, Keycloak et API d’administration.
- [x] Royaume Keycloak, rôles `admin` / `agent`, TOTP obligatoire.
- [x] OIDC Synapse–Keycloak, inscription Matrix et accès invité désactivés.
- [ ] Test de révocation à deux appareils et note de sécurité mise à jour.

### Preuves locales déjà obtenues

- Les six services Compose sont `healthy` ; seuls les ports 80 et 443 de Caddy
  sont publiés sur l’hôte. PostgreSQL, Synapse, Keycloak et l’API restent
  accessibles uniquement sur le réseau interne Compose.
- Le parcours réel Keycloak → Element a été validé avec un compte fictif :
  changement du mot de passe temporaire puis configuration TOTP.
- Le realm versionné déclare les actions requises `CONFIGURE_TOTP` et
  `UPDATE_PASSWORD`. Synapse utilise la copie lisible de la CA locale Caddy
  pour ses appels OIDC HTTPS ; aucun certificat privé n’est ajouté au dépôt.

### Preuves encore à obtenir

- Tester l’adresse unique depuis un second appareil, idéalement un téléphone,
  après installation de la CA locale.
- Révoquer un agent connecté sur deux appareils et vérifier la perte d’accès
  aux nouveaux messages.
- Tester l’enrôlement réel avec un jeton PKCE du client `console`. Cette
  preuve dépend de la console ou d’un harnais PKCE, relevant du produit B.

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
