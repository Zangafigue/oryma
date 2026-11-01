# Oryma — Messagerie souveraine de l’administration

**Oryma** est une messagerie instantanée destinée aux agents de l’administration publique du Burkina Faso (messages, groupes, fichiers). Elle est hébergeable sur l’infrastructure de l’État, chiffrée de bout en bout et conçue pour qu’un serveur compromis ou curieux ne puisse lire aucun message. Son identifiant technique historique est `msgsov`.

Le nom est une création de l’équipe : il désigne un espace d’échange fiable, structuré et durable, au service d’une administration qui maîtrise ses données et ses outils numériques. Il n’emprunte volontairement aucune étymologie locale non validée.

Le projet répond au sprint technique pré-hackathon 2026 (Hackathon 226, MTDPCE – DGTD), challenge « La messagerie souveraine de l’administration ».

## État du projet

Le projet est en phase de cadrage. Le dépôt contient la documentation de référence ; le code est initialisé pendant le sprint. Chaque commande ci-dessous est une **cible** tant qu’elle n’a pas été vérifiée sur une installation propre.

## Concept

Un agent se connecte avec son compte professionnel et un second facteur (TOTP), puis échange des messages et des fichiers chiffrés dans Element. Un administrateur enrôle les agents et peut révoquer immédiatement un agent sur tous ses appareils. Une salle peut être classifiée (Diffusion restreinte, Confidentiel) ; ses messages expirent alors côté serveur à l’échéance du niveau.

## Architecture

```text
Navigateur ──HTTPS──> Caddy (seul port publié)
                        ├──> Element Web
                        ├──> Synapse ──> PostgreSQL (base synapse)
                        │      └─ OIDC ─> Keycloak ──> PostgreSQL (base keycloak)
                        └──> API d’administration (FastAPI) ──> Keycloak, Synapse, PostgreSQL (base adminapi)
```

Six conteneurs : `caddy`, `element`, `synapse`, `keycloak`, `postgres`, `admin-api`. Détails dans [docs/architecture](docs/architecture/system-architecture.md).

## Technologies et licences

| Composant | Rôle | Licence (à vérifier sur le dépôt officiel) |
|---|---|---|
| [Synapse](https://github.com/element-hq/synapse) | Serveur Matrix | AGPL-3.0 |
| [Element Web](https://github.com/element-hq/element-web) | Client web | AGPL-3.0 |
| [Keycloak](https://www.keycloak.org/) | Identité, TOTP, rôles | Apache-2.0 |
| [PostgreSQL](https://www.postgresql.org/) | Bases de données | PostgreSQL License |
| [Caddy](https://caddyserver.com/) | Proxy inverse, TLS interne | Apache-2.0 |
| [FastAPI](https://fastapi.tiangolo.com/) | API d’administration | MIT |
| [pytest](https://pytest.org/) | Tests | MIT |
| Docker Compose | Déploiement | Apache-2.0 |

Chiffrement : protocole **Matrix (Olm/Megolm)**, fourni par les bibliothèques d’Element. **Aucune cryptographie n’est écrite par l’équipe.**

## Niveau d’engagement open source

**Étendre et adapter** : assemblage et configuration de Synapse et Element, plus un service d’administration écrit par l’équipe (enrôlement, révocation, salles classifiées, audit).

## Installation (cible)

```bash
cp .env.example .env     # puis renseigner les secrets générés
docker compose up -d
```

Aucun service tiers n’est nécessaire au fonctionnement. Les comptes de démonstration sont fictifs et décrits dans [docs/demo/mvp-scenario.md](docs/demo/mvp-scenario.md). Le guide complet, y compris le certificat pour téléphone, est dans [docs/deployment](docs/deployment/README.md).

## Limites connues

- Le serveur voit des métadonnées : qui est dans quelle salle, quand, la taille des messages et le niveau de chaque salle.
- Un agent révoqué garde ce qu’il a déjà reçu sur son appareil ; seuls les nouveaux messages lui sont fermés.
- La purge à expiration supprime la copie du serveur, pas celle d’un appareil qui l’a déjà reçue.
- Applications natives et notifications en arrière-plan non couvertes ; le client web s’installe sur l’écran d’accueil.
- Pas de montée en charge, ni de fédération, ni d’archivage légal dans le prototype.

La note complète est dans [docs/securite.md](docs/securite.md).

## Pour commencer

1. Lire [le cadrage](PROJECT_OVERVIEW.md).
2. Suivre [le parcours documentaire](docs/README.md).
3. Utiliser [le guide de développement à deux](docs/development/README.md).
4. Consulter [les règles de contribution](CONTRIBUTING.md).

## Sécurité

Ne publiez jamais une vulnérabilité ou un secret dans une issue publique. Suivez [SECURITY.md](SECURITY.md).

## Licence

AGPL-3.0, voir [LICENSE](LICENSE).
