# msgsov — Spécification de l’API d’administration

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>architecture/system-architecture.md</code></p>

L’API est consommée par la console d’administration. Les appels vers Keycloak et Synapse sont décrits dans [system-architecture.md](../architecture/system-architecture.md) ; leurs noms de routes et d’options sont à vérifier dans la documentation des versions retenues.

## 1. Conventions

Voir le [registre](README.md). Base `/api/v1`, JSON `snake_case`, UUID, dates ISO 8601.

### Authentification

Jeton porteur émis par Keycloak (`Authorization: Bearer …`). Le service valide la signature (JWKS), l’émetteur, l’audience et l’expiration, puis lit le rôle dans `realm_access.roles`. Les valeurs exactes et les trois clients sont dans le [contrat OIDC](keycloak-oidc.md). Le contrôle est fait dans une dépendance commune.

### Enveloppe de succès

```json
{
  "data": {},
  "request_id": "7b1c2d34-0f1e-4a8b-9c3d-2e5f6a7b8c9d"
}
```

Les collections ajoutent `next_cursor` (nul à la dernière page).

### Enveloppe d’erreur

Voir le registre. Codes : [software-requirements.md](../product/software-requirements.md).

## 2. Santé et profil

### GET `/health`

Réseau interne uniquement. Réponse :

```json
{ "status": "ok", "checks": { "database": "ok", "keycloak": "ok", "synapse": "ok" } }
```

### GET `/me`

Rôle : `agent` ou `admin`. Retourne l’agent associé au jeton.

```json
{ "data": { "id": "…", "nom_complet": "Agent Démo 1", "role": "agent", "statut": "actif" }, "request_id": "…" }
```

## 3. Agents

### POST `/agents`

Rôle : `admin`. Enrôle un agent.

Corps :

```json
{
  "identifiant": "agent.demo1",
  "nom_complet": "Agent Démo 1",
  "ministere_code": "MIN-DEMO-A",
  "fonction": "Chargé d’études",
  "role": "agent"
}
```

Effets : création de l’utilisateur Keycloak (activé, TOTP à configurer, rôle affecté, mot de passe temporaire à changer), enregistrement dans `agents`, ligne d’audit `ENROLEMENT`.

Réponse `201` : l’agent et `mot_de_passe_temporaire`, **affiché une seule fois, jamais stocké ni journalisé**, à transmettre par un canal convenu.

Erreurs : `ERR-013`, `ERR-014`, `ERR-021` si le ministère est introuvable, `ERR-022` si l’identifiant est déjà utilisé, `ERR-023` si le corps est invalide, `ERR-500`.

Le rôle est strictement limité à `admin` ou `agent`. Si une étape échoue après la création Keycloak mais avant l’écriture complète en base, le compte Keycloak est désactivé ou supprimé en compensation afin d’éviter un compte orphelin.

### GET `/agents`

Rôle : `admin` actif. Filtres optionnels : `statut` (`actif` ou `revoque`), `ministere_code`. Pagination par curseur opaque (`page_size` de 1 à 100, 50 par défaut).

Réponse : `{ "data": { "items": [Agent], "next_cursor": "…" }, "request_id": "…" }`. `next_cursor` est nul à la dernière page. Les agents sont parcourus dans l’ordre stable de leur UUID.

### GET `/agents/{agent_id}`

Rôle : `admin` actif. Retourne un `Agent`. Erreur `ERR-031` si l’agent est introuvable.

### PATCH `/agents/{agent_id}/role`

Rôle : `admin` actif. Corps strict : `{ "role": "admin" }` (valeurs permises : `admin`, `agent`). Le service remplace le rôle realm Keycloak puis met à jour `agents` et écrit l’audit `CHANGEMENT_ROLE` dans une transaction. Si l’écriture en base échoue après la mise à jour Keycloak, le rôle Keycloak est compensé ; un échec de compensation est signalé en `ERR-500`. Une demande conservant le rôle courant est idempotente et ne crée pas d’entrée d’audit. Erreurs : `ERR-013`, `ERR-014`, `ERR-023`, `ERR-031`, `ERR-500`.

### POST `/agents/{agent_id}/revoke`

Rôle : `admin`. Lance la séquence de révocation ([INV-06](../architecture/system-contract.md)).

Réponse `200` lorsque toutes les étapes réussissent :

```json
{
  "data": {
    "agent_id": "…",
    "statut_operation": "complete",
    "etapes": [
      { "ordre": 1, "nom": "keycloak_desactivation", "statut": "reussie" },
      { "ordre": 2, "nom": "keycloak_sessions", "statut": "reussie" },
      { "ordre": 3, "nom": "synapse_appareils", "statut": "reussie" },
      { "ordre": 4, "nom": "synapse_desactivation", "statut": "reussie" },
      { "ordre": 5, "nom": "base_statut", "statut": "reussie" },
      { "ordre": 6, "nom": "audit", "statut": "reussie" }
    ]
  },
  "request_id": "…"
}
```

En cas d’échec d’une étape : réponse `502` avec `ERR-033` et `details.etapes` (l’étape en échec et les suivantes `ignoree`). Un nouvel appel reprend sans répéter les effets déjà réalisés. Un agent déjà révoqué retourne `200` avec son état (`ERR-032` n’est pas une erreur bloquante), sans effet de bord.

## 4. Salles classifiées

### GET `/levels`

Rôle : `agent`. Liste des niveaux (`code`, `libelle`, `duree_vie_secondes`).

### POST `/rooms`

Rôle : `agent` ou `admin`. Corps :

```json
{ "nom": "Réunion DG", "niveau": "CONFIDENTIEL", "membres": ["<agent_id>", "<agent_id>"] }
```

Le service refuse si l’appelant ou un membre n’est pas un agent actif (`ERR-042`), si le niveau est inconnu (`ERR-041`). Il crée la salle via le compte de service ([ADR-008](../adr/008-classified-rooms-service-account.md)) avec le chiffrement et la rétention dans l’état initial, puis enregistre `salles` et l’audit `CREATION_SALLE`. `salles.duree_vie_secondes` conserve la durée effectivement appliquée comme instantané ; `niveaux_classification` reste la source de vérité pour les nouvelles salles. Le nom retourné porte le niveau (par exemple « [Confidentiel] Réunion DG »).

Réponse `201` : `{ "room_id": "…", "nom": "…", "niveau": "CONFIDENTIEL", "duree_vie_secondes": 86400 }`. En cas d’échec avant le `201` après création côté Synapse, le service tente une suppression via un accès d’administration distinct et limité. Erreur `ERR-043` si la création ou la compensation échoue ; si la suppression échoue, aucune salle n’est enregistrée comme créée et une trace technique est conservée dans `reconciliation_salles`.

### GET `/rooms`

Rôle : `agent`. « Mes salles » : salles créées par l’appelant avec niveau et durée de vie.

## 5. Audit

### GET `/audit`

Rôle : `admin`. Filtres : `action`, `acteur_id`, `depuis`, `jusqu_a`. Lecture seule. Pas d’adresse IP ni de contenu de message.

Un `403` pour rôle insuffisant écrit `TENTATIVE_ACCES_REFUSE`, avec la route et le motif uniquement. Ni l’adresse IP, ni le jeton, ni un identifiant de session ne sont journalisés.

## 6. Annuaire

`GET /directory` est **coupé** du prototype (priorité Could).

## 7. Appels sortants

| Cible | Usage | Compte |
|---|---|---|
| Keycloak (API REST d’administration) | Créer, désactiver, fermer les sessions | Client `admin-api` |
| Synapse (API d’administration) | Supprimer les appareils, désactiver un compte | Compte de service d’administration |
| Synapse (API client Matrix) | Créer une salle avec chiffrement et rétention, inviter, quitter | Compte de service des salles, sans droits d’administration |

## 8. Référence des types

| Type | Champs |
|---|---|
| `Agent` | `id`, `identifiant`, `matrix_id`, `nom_complet`, `ministere_code`, `fonction`, `role`, `statut`, `cree_le`, `revoque_le` |
| `Salle` | `room_id`, `nom`, `niveau`, `duree_vie_secondes`, `cree_le` |
| `NiveauClassification` | `code`, `libelle`, `duree_vie_secondes`, `transfert_interdit` |
| `EtapeRevocation` | `ordre`, `nom`, `statut` (`reussie`, `echec`, `ignoree`), `detail` |
| `AuditEvent` | `id`, `horodatage`, `action`, `acteur_id`, `cible_id`, `details` |

`transfert_interdit` est indicatif : il décrit une règle d’usage affichée dans l’interface et n’empêche pas techniquement la copie d’un message.

## 9. Résumé des propriétaires

| Route | Rôle requis | Propriétaire |
|---|---|---|
| `GET /health` | interne | AdminService |
| `GET /me` | agent | AdminService |
| `POST/GET /agents`, `PATCH …/role` | admin | EnrollmentService |
| `POST /agents/{id}/revoke` | admin | RevocationService |
| `GET /levels`, `POST/GET /rooms` | agent | RoomService |
| `GET /audit` | admin | AuditLedger |
