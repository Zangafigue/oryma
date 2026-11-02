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
| Authentification par jeton Keycloak | AdminService / B | Console | Accepté | Test jeton valide, invalide, expiré, mauvaise audience et mauvais rôle |
| `POST /agents` (enrôlement) | EnrollmentService / B | Console | Accepté | OpenAPI + test d’intégration avec TOTP imposé |
| `GET /agents` et `GET /agents/{id}` | AgentManagementService / B | Console | Implémenté | Tests de filtre, pagination, autorisation et agent introuvable |
| `POST /agents/{id}/revoke` | RevocationService / B | Console | Accepté | Test de révocation à deux appareils + test d’idempotence |
| `POST /rooms` et `GET /rooms` | RoomService / B | Console | Accepté | Test de création de salle + purge à l’échéance |
| `GET /audit` | AuditLedger / B | Console | Proposé | Test en ajout seul |
| `GET /health` | AdminService / B | Deployment / A | Proposé | Contrôle d’état dans Compose |
| Royaume Keycloak (clients et rôles) | IdentityProvider / A | AdminService / B | Accepté | `realm-export.json` + test de connexion |
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

### Contrat du jeton Keycloak consommé par l’API

- Issuer exact : `https://${ORYMA_HOST}/auth/realms/oryma`.
- Découverte OIDC : `https://${ORYMA_HOST}/auth/realms/oryma/.well-known/openid-configuration`.
- JWKS public : `https://${ORYMA_HOST}/auth/realms/oryma/protocol/openid-connect/certs`.
- Audience obligatoire : `admin-api`.
- Client appelant : `console`; le jeton doit porter `azp: console` et `typ: Bearer`.
- Signature RS256 vérifiée avec le JWKS Keycloak ; `exp` requis et `nbf` vérifié s’il est présent.
- Les rôles proviennent uniquement de `realm_access.roles`. Les opérations sensibles exigent `admin`.
- En Compose, l’API récupère le même JWKS via le nom de service interne `keycloak`; cet accès réseau ne change pas la validation de l’issuer public.
- Le client de service `admin-api` utilise ses credentials client uniquement pour l’API d’administration Keycloak. Son compte de service doit recevoir dans le royaume `oryma` les rôles `manage-users`, `query-users` et `view-realm` nécessaires à l’enrôlement ; il ne remplace jamais le client utilisateur `console` pour valider `azp`.
- Un refus de rôle répond `403` (`ERR-014`) et inscrit `TENTATIVE_ACCES_REFUSE` avec uniquement la route et le motif `ROLE_INSUFFISANT`.

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
