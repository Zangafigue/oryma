# Index d’architecture et limites des modules

La description détaillée du système se trouve dans [system-architecture.md](system-architecture.md). Cet index transforme cette architecture en règles de collaboration pour les deux membres.

## Composants et responsables d’implémentation

| Composant | Responsabilité | Responsable principal | Coordination nécessaire avec |
|---|---|---|---|
| Deployment (Docker Compose) | Réseaux, volumes, secrets, contrôles d’état, installation en une commande | A | Tous |
| EdgeProxy (Caddy) | Point d’entrée unique, TLS interne, en-têtes de sécurité, journaux minimaux | A | AgentClient, AdminService |
| MessageServer (Synapse) | Transport et stockage chiffrés, rétention, réglages de métadonnées | A | IdentityProvider, AdminService |
| IdentityProvider (Keycloak) | SSO, TOTP, rôles, comptes de démonstration fictifs | A | MessageServer, AdminService |
| AgentClient (Element Web) | Chiffrement, vérification des appareils, thème et textes | B | MessageServer, EdgeProxy |
| AdminService — EnrollmentService | Enrôlement, changement de rôle | B | IdentityProvider, Store |
| AdminService — RevocationService | Séquence de révocation | B | IdentityProvider, MessageServer |
| AdminService — RoomService | Salles classifiées, rétention | B | MessageServer, Store |
| AdminService — Console | Pages A1 à A5 | B | Tous les services d’AdminService |
| AuditLedger | Journal d’audit en ajout seul | B | Chaque service émetteur |
| Store (PostgreSQL) | Trois bases et leurs comptes | A (instance), B (schéma `adminapi`) | AdminService |

Le responsable principal conduit l’implémentation ; il n’est pas propriétaire exclusif des décisions. Les invariants restent attribués aux composants dans [requirements-traceability.md](requirements-traceability.md).

## Direction des dépendances

```text
Console et routes HTTP
            ↓
Services applicatifs (enrôlement, révocation, salles)
            ↓
Clients d’API (Keycloak, Synapse) et accès base
            ↓
Keycloak / Synapse / PostgreSQL
```

- Une route valide le jeton et le rôle, appelle un service et traduit le résultat HTTP ; elle ne contient pas la règle métier.
- Un service applicatif ne dépend ni de FastAPI ni de la console.
- Les clients Keycloak et Synapse sont isolés derrière des interfaces simulables dans les tests.
- Aucun module n’écrit dans les tables de Synapse ou de Keycloak : ils passent par leurs API.
- La console consomme l’API d’administration ; elle ne contient aucune règle de sécurité.

## Interfaces entre composants

| Producteur | Consommateur | Interface | Contrat |
|---|---|---|---|
| IdentityProvider | MessageServer | OIDC | Royaume `msgsov`, client `synapse` |
| IdentityProvider | AdminService | OIDC et API REST d’administration | Clients `console` et `admin-api` |
| AdminService | MessageServer | API d’administration et API client Matrix | Deux comptes de service distincts |
| AdminService | Store | SQL | [data-dictionary.md](../data/data-dictionary.md) |
| EdgeProxy | Tous | Proxy inverse | [deployment/README.md](../deployment/README.md) |

## Règles de changement

- Un nouveau composant ou un changement de propriétaire d’invariant met à jour ce document, la traçabilité et les tests concernés.
- Un contrat partagé garde son statut dans le [registre API](../api/README.md).
