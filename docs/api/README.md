# Registre des contrats API

- **Version :** v0.1, 2026-11-01
- **Statut :** Proposé comme cadre de conception — chaque contrat du registre conserve son propre statut jusqu’à sa preuve exécutable

## Rôle de ce dossier

La [spécification API initiale](specification.md) décrit l’ensemble du contrat HTTP du service d’administration. Ce dossier sert au travail quotidien : statut des contrats, responsabilités, règles d’évolution.

Il ne doit pas devenir une seconde spécification contradictoire.

## Hiérarchie des sources

| Ordre | Source | Rôle |
|---:|---|---|
| 1 | OpenAPI généré par FastAPI | Contrat HTTP exécutable dès que le service existe |
| 2 | Tests de contrat et fixtures JSON | Preuve que producteur, simulation et consommateur utilisent le même schéma |
| 3 | [specification.md](specification.md) | Intention, conventions et contrat de conception initial |
| 4 | Ce registre | Statut, propriété, transitions |

Toute divergence est corrigée dans la même pull request.

## Conventions non négociables

- Base : `/api/v1`.
- JSON en UTF-8 et champs en `snake_case`.
- Identifiants UUID opaques.
- Dates ISO 8601 avec fuseau.
- Collections paginées par curseur opaque avec `page_size` borné (100 au maximum).
- Erreurs structurées avec code machine stable, message humain et détails filtrés.
- `X-Request-ID` sur chaque réponse.
- L’identité de l’appelant vient du jeton, jamais du corps de la requête.
- Aucune réponse ni aucun journal ne contient de contenu de message.

## Registre initial

| Contrat | Producteur | Consommateur | Statut | Preuve attendue |
|---|---|---|---|---|
| Authentification par jeton Keycloak | AdminService / B | Console | Proposé | Test jeton valide, expiré, mauvais rôle |
| `POST /agents` (enrôlement) | EnrollmentService / B | Console | Proposé | OpenAPI + test d’intégration avec TOTP imposé |
| `POST /agents/{id}/revoke` | RevocationService / B | Console | Proposé | Test de révocation à deux appareils + test d’idempotence |
| `POST /rooms` et `GET /rooms` | RoomService / B | Console | Proposé | Test de création de salle + purge à l’échéance |
| `GET /audit` | AuditLedger / B | Console | Proposé | Test en ajout seul |
| `GET /health` | AdminService / B | Deployment / A | Proposé | Contrôle d’état dans Compose |
| Royaume Keycloak (clients et rôles) | IdentityProvider / A | AdminService / B | Proposé | `realm-export.json` + test de connexion |
| `GET /directory` | — | — | Coupé | — |

Le nom après `/` indique le responsable humain principal selon `CONTRIBUTING.md` ; le nom avant `/` est le composant propriétaire.

## Contenu minimal d’un contrat accepté

- producteur et consommateur nommés ;
- schéma d’entrée et de sortie ;
- codes d’erreur stables ;
- exemple complet ;
- règle d’autorisation ;
- test exécutable ;
- accord du consommateur.

## Format d’erreur commun

```json
{
  "error": {
    "code": "ERR-014",
    "message": "Rôle insuffisant pour cette opération.",
    "details": {}
  },
  "request_id": "7b1c2d34-0f1e-4a8b-9c3d-2e5f6a7b8c9d"
}
```

## Processus contract-first

1. Le producteur propose le contrat dans ce registre et dans la spécification.
2. Le consommateur l’accepte ou le conteste.
3. Une fixture JSON et une simulation sont publiées.
4. L’implémentation et les tests de contrat passent.
5. Le statut passe à Vérifié.

Statuts : Proposé → Accepté → Implémenté → Vérifié.

## Évolution et compatibilité

### Compatible

- Ajout d’un champ optionnel en réponse.
- Ajout d’une route.

### Incompatible

- Suppression ou renommage d’un champ.
- Changement de sémantique d’un code d’erreur.
- Modification du rôle requis.

Un changement incompatible passe par un nouvel ADR ou une nouvelle version de route.

## Checklist de revue

- [ ] Le rôle requis est vérifié côté serveur.
- [ ] L’identité vient du jeton.
- [ ] Les erreurs utilisent les codes du [SRS](../product/software-requirements.md).
- [ ] Aucune donnée sensible n’est renvoyée sans nécessité.
- [ ] Les exemples utilisent des comptes fictifs.
- [ ] L’action est écrite dans l’audit lorsqu’elle est sensible.
