# Architecture Decision Records

Les ADRs conservent le contexte, la décision, les alternatives et les conséquences des choix techniques structurants de msgsov.

## Index

| ADR | Statut | Décision |
|---|---|---|
| [ADR-001](001-matrix-protocol.md) | Accepté | Matrix comme protocole de messagerie chiffrée |
| [ADR-002](002-synapse-element.md) | Accepté | Synapse et Element Web configuré, sans fork profond |
| [ADR-003](003-keycloak-identity.md) | Accepté | Keycloak pour l’identité, le second facteur et les rôles |
| [ADR-004](004-postgresql-three-databases.md) | Accepté | PostgreSQL 16 avec trois bases |
| [ADR-005](005-caddy-internal-tls.md) | Accepté | Caddy avec certificat interne comme proxy inverse |
| [ADR-006](006-fastapi-admin-service.md) | Accepté | FastAPI pour le service d’administration |
| [ADR-007](007-docker-compose.md) | Accepté | Docker Compose pour l’installation en une commande |
| [ADR-008](008-classified-rooms-service-account.md) | Accepté | Création des salles classifiées par un compte de service sans droits d’administration |
| [ADR-009](009-installable-web-client.md) | Accepté | Client web installable plutôt qu’applications natives |
| [ADR-010](010-agpl-licence.md) | Accepté | Dépôt sous licence AGPL-3.0 |

## Cycle de vie

```text
PROPOSÉ → ACCEPTÉ → REMPLACÉ ou DÉPRÉCIÉ
```

- Ne supprimez pas un ADR accepté.
- Une décision différente crée un nouvel ADR qui référence celui qu’elle remplace.
- Un changement de statut, de conséquence ou de contexte passe par une pull request.
- Utilisez [template.md](template.md) pour une nouvelle décision et continuez la numérotation.
