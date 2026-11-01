# msgsov — Architecture système

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>architecture/requirements-traceability.md</code></p>

## Style architectural

Assemblage de briques open source derrière un point d’entrée unique, avec un petit service d’administration écrit par l’équipe. Le chiffrement est réalisé sur l’appareil ; le serveur ne manipule que des événements chiffrés.

```text
Navigateur ──HTTPS──> Caddy (443)
                        ├──> Element Web (fichiers statiques)
                        ├──> Synapse ──────> PostgreSQL (base synapse)
                        │       └─ OIDC ───> Keycloak ──> PostgreSQL (base keycloak)
                        └──> API d’administration (FastAPI)
                                ├──> Keycloak (API REST)
                                ├──> Synapse (API d’administration et API client)
                                └──> PostgreSQL (base adminapi)
```

## Architecture des composants

### EdgeProxy (Caddy)

Termine TLS avec un certificat interne, route vers Element, Synapse, Keycloak (hors console d’administration) et l’API d’administration. En-têtes de sécurité (HSTS, CSP, `X-Frame-Options`, `Referrer-Policy: no-referrer`). Journaux d’accès désactivés ou sans adresse IP.

### MessageServer (Synapse)

Serveur Matrix : transport et stockage d’événements chiffrés, comptes, salles, appareils. Inscription et accès invité désactivés, mot de passe local désactivé, fournisseur OIDC Keycloak, fédération désactivée, présence et aperçus d’URL désactivés, conservation courte des adresses IP, rétention activée.

### IdentityProvider (Keycloak)

Royaume `msgsov` : rôles `admin` et `agent`, action requise « Configure OTP », protection anti-force brute, durée de session courte. Clients OIDC : `synapse`, `console` et `admin-api`. Console d’administration de Keycloak non routée par le proxy.

### AgentClient (Element Web)

Client configuré (`config.json`) et habillé. Chiffrement par défaut, vérification des appareils, sauvegarde des clés. Installable sur l’écran d’accueil.

### AdminService (FastAPI)

Enrôlement, révocation, salles classifiées, journal d’audit, annuaire facultatif, point `/health`. Il sert aussi la console d’administration.

### AuditLedger

Table `audit_log` alimentée par chaque action d’administration ; lecture réservée aux administrateurs ; pas d’adresse IP ni de contenu.

### Store (PostgreSQL)

Un conteneur, trois bases (`synapse`, `keycloak`, `adminapi`), un compte par base.

## Architecture des données

La base `adminapi` contient les tables métier et la trace technique de réconciliation des créations de salles. Synapse et Keycloak gèrent leurs propres tables.

```text
ministeres 1───n agents 1───n audit_log (acteur, cible)
niveaux_classification 1───n salles n───1 agents (créateur)
salles ──> reconciliation_salles (room_id si compensation échouée)
```

### Contraintes structurantes

- `agents.keycloak_id` et `agents.matrix_id` sont uniques.
- Une salle porte au plus un niveau.
- `audit_log` n’accepte que des insertions et des lectures pour le compte du service.
- Aucune colonne ne stocke de contenu de message ni d’adresse IP.

Détails : [data-dictionary.md](../data/data-dictionary.md).

## Flux principaux

### Enrôlement d’un agent

1. L’administrateur envoie `POST /api/v1/agents` depuis la console.
2. Le service valide jeton et rôle `admin`.
3. Il crée l’utilisateur Keycloak (activé, TOTP à configurer, rôle affecté).
4. Il enregistre l’agent dans `adminapi` avec son identifiant Matrix.
5. Il écrit la ligne d’audit.
6. À sa première connexion, l’agent configure son TOTP puis arrive sur Element.

### Connexion d’un agent

Element redirige vers Keycloak (identifiant, mot de passe, TOTP). Keycloak émet l’identité vers Synapse (OIDC). Un compte inconnu ou désactivé est refusé à Keycloak.

### Envoi d’un message chiffré

1. Element chiffre le message sur l’appareil (Megolm).
2. Le message chiffré part vers Synapse, qui le stocke et le transmet.
3. L’appareil du destinataire le reçoit et le déchiffre.

### Révocation d’un agent

L’ordre compte : on ferme d’abord la porte d’entrée.

1. Keycloak : désactiver l’utilisateur.
2. Keycloak : fermer toutes ses sessions.
3. Synapse : supprimer tous ses appareils (invalide ses jetons d’accès).
4. Synapse : désactiver le compte (le retire des salles).
5. `adminapi` : statut `revoque`, date et auteur.
6. Audit : ligne `REVOCATION`.

Chaque étape est rejouable. Le résultat étape par étape est retourné à la console. Les clients des autres membres renouvellent la clé de session de groupe : comportement à vérifier par test à deux appareils.

### Création d’une salle classifiée

1. L’agent ouvre l’écran A5 et choisit le nom, les membres et le niveau.
2. `POST /api/v1/rooms` vérifie que l’agent et chaque membre sont des agents actifs.
3. Le service appelle l’API client Matrix de création de salle avec le compte de service sans droits d’administration : salle privée, événement de chiffrement et politique de rétention du niveau dans l’état initial, agent demandeur au niveau de pouvoir administrateur, membres invités.
4. Le compte de service quitte la salle ; les invitations restent valables.
5. Le service enregistre la salle dans `salles` et écrit l’audit.
6. À l’échéance, Synapse purge les anciens messages de la base du serveur.

**À tester en premier** (environ 30 minutes, dès que Synapse démarre) : création avec chiffrement et rétention via `curl`, vérification dans Element, purge après une durée de démonstration courte. **Plan B** : voir [ADR-008](../adr/008-classified-rooms-service-account.md).

### Épreuve « Le serveur ne lit rien »

Un message contenant une phrase repère est envoyé ; l’export de la base `synapse` n’en contient aucune trace lisible ; la capture du trafic entre Caddy et Synapse ne montre que du contenu chiffré.

## Budgets initiaux

| Mesure | Cible |
|---|---|
| Envoi et réception d’un message, réseau local | moins de 2 secondes |
| Révocation de bout en bout | quelques secondes, résultat visible étape par étape |
| Premier message d’un nouvel agent | moins de 3 minutes |
| Mémoire de la machine d’hébergement | 4 Go recommandés, 2 Go au minimum |

Ces valeurs sont des cibles à mesurer, pas des résultats.

## Correspondance technologique

| Composant | Technologie | Licence (à vérifier) |
|---|---|---|
| EdgeProxy | Caddy | Apache-2.0 |
| MessageServer | Synapse | AGPL-3.0 |
| AgentClient | Element Web | AGPL-3.0 |
| Chiffrement | Bibliothèques d’Element (matrix-sdk-crypto, matrix-js-sdk) | Apache-2.0 |
| IdentityProvider | Keycloak | Apache-2.0 |
| AdminService | FastAPI | MIT |
| Store | PostgreSQL 16 | PostgreSQL License |
| Déploiement | Docker Compose | Apache-2.0 |
| Tests | pytest | MIT |

## Architecture de déploiement

| Service | Rôle | Port exposé |
|---|---|---|
| `caddy` | Proxy inverse, TLS interne | 443 (80 pour la redirection) |
| `element` | Client | aucun |
| `synapse` | Serveur Matrix | aucun |
| `keycloak` | Identité, TOTP, rôles | aucun |
| `postgres` | Trois bases | aucun |
| `admin-api` | Enrôlement, révocation, salles, audit | aucun |

Réseau `externe` : Caddy seulement. Réseau `interne` sans accès sortant : tous les autres. Volumes nommés : données PostgreSQL, médias de Synapse, données de Caddy. Détails : [deployment/README.md](../deployment/README.md).

## Structure cible du projet

```text
/docker-compose.yml
/.env.example
/caddy/Caddyfile
/synapse/homeserver.yaml
/keycloak/realm-export.json
/element/config.json
/admin-api/            (FastAPI, migrations SQL, tests pytest)
/docs/securite.md
/README.md  /LICENSE
```

## Matrice de traçabilité

Voir [requirements-traceability.md](requirements-traceability.md) pour l’attribution de chaque invariant à un composant et [testing/README.md](../testing/README.md) pour les tests correspondants.

## Contraintes et décisions

- Aucune cryptographie écrite par l’équipe ([ADR-001](../adr/001-matrix-protocol.md)).
- Aucun fork profond d’Element ([ADR-002](../adr/002-synapse-element.md)).
- Identité déléguée à Keycloak ([ADR-003](../adr/003-keycloak-identity.md)).
- Salles classifiées créées par un compte de service ([ADR-008](../adr/008-classified-rooms-service-account.md)).
- Client web installable, pas d’applications natives ([ADR-009](../adr/009-installable-web-client.md)).
