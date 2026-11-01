# Oryma — Vue d’ensemble du projet

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Statut :</strong> source de cadrage initiale</p>

## 1. Présentation du projet

**Oryma** est une messagerie instantanée souveraine pour les agents de l’administration publique du Burkina Faso. Elle propose des messages individuels et de groupe et l’envoi de fichiers, avec un chiffrement de bout en bout, sur une infrastructure maîtrisée par l’État. L’identifiant technique historique du projet est `msgsov`.

Elle ne réinvente ni le protocole ni le chiffrement : elle assemble des briques open source éprouvées (Matrix, Synapse, Element, Keycloak, Caddy, PostgreSQL) et ajoute ce qui manque pour un usage administratif : enrôlement contrôlé, second facteur, révocation immédiate, salles classifiées avec expiration et journal d’audit.

Le projet est le prototype du **sprint technique pré-hackathon 2026** (MTDPCE – DGTD), challenge « La messagerie souveraine de l’administration ».

---

## 2. Problème traité

| Problème | Conséquence |
|---|---|
| Échanges de service sur des messageries grand public aux serveurs hors de contrôle | Perte de maîtrise des données et des règles |
| Aucun contrôle des accès quand un agent part ou perd son téléphone | Fuite possible d’informations |
| Pas de distinction entre message courant et message sensible | Informations sensibles conservées indéfiniment |

---

## 3. Objectifs du projet

### 3.1 Objectif principal

Doter l’administration d’une messagerie aussi simple que les applications du marché, mais conçue pour la sécurité des échanges administratifs.

### 3.2 Objectifs du prototype

1. Messages, groupes et fichiers chiffrés de bout en bout.
2. Serveur incapable de lire un message ou un fichier.
3. Installation en une seule commande, sans service tiers.
4. Identité vérifiée : enrôlement préalable, TOTP obligatoire, rôles.
5. Révocation immédiate d’un agent sur tous ses appareils.
6. Une fonctionnalité innovante démontrée : salles classifiées avec expiration automatique.
7. Utilisation sur ordinateur et téléphone.

---

## 4. Périmètre

### 4.1 Inclus

- Messages 1-à-1, groupes et fichiers chiffrés.
- Enrôlement par un administrateur, TOTP, rôles `admin` et `agent`.
- Révocation sur tous les appareils.
- Salles classifiées (Diffusion restreinte, Confidentiel) avec rétention côté serveur.
- Journal d’audit des actions d’administration.
- Console d’administration légère.
- Client web adapté aux petits écrans, installable sur l’écran d’accueil.
- Interface en langue nationale (bonus).

### 4.2 Hors périmètre

- Appels audio et vidéo.
- Fédération avec d’autres serveurs Matrix.
- Applications natives Android et iOS.
- Notifications en arrière-plan (service tiers).
- Archivage légal, effacement à distance, montée en charge (workers, répartition de charge).
- Annuaire et WebAuthn (coupés).

---

## 5. Architecture générale

```text
Navigateur ──HTTPS──> Caddy (443)
                        ├──> Element Web (fichiers statiques)
                        ├──> Synapse ──────> PostgreSQL (synapse)
                        │       └─ OIDC ───> Keycloak ──> PostgreSQL (keycloak)
                        └──> API d’administration (FastAPI)
                                ├──> Keycloak (API REST)
                                ├──> Synapse (API d’administration et API client)
                                └──> PostgreSQL (adminapi)
```

Le chiffrement se fait **sur l’appareil** (Element). Synapse transporte et stocke uniquement du contenu chiffré. Voir [system-architecture.md](docs/architecture/system-architecture.md).

---

## 6. Stack technique retenue

| Couche | Choix | ADR |
|---|---|---|
| Protocole | Matrix (Olm/Megolm), « Étendre et adapter » | [001](docs/adr/001-matrix-protocol.md) |
| Serveur et client | Synapse, Element Web configuré | [002](docs/adr/002-synapse-element.md) |
| Identité | Keycloak (OIDC), TOTP, rôles | [003](docs/adr/003-keycloak-identity.md) |
| Base de données | PostgreSQL 16, trois bases | [004](docs/adr/004-postgresql-three-databases.md) |
| Proxy et TLS | Caddy, `tls internal` | [005](docs/adr/005-caddy-internal-tls.md) |
| Service d’administration | FastAPI (Python) | [006](docs/adr/006-fastapi-admin-service.md) |
| Déploiement | Docker Compose | [007](docs/adr/007-docker-compose.md) |
| Salles classifiées | Compte de service sans droits d’administration | [008](docs/adr/008-classified-rooms-service-account.md) |
| Mobile | Client web installable | [009](docs/adr/009-installable-web-client.md) |
| Licence | AGPL-3.0 | [010](docs/adr/010-agpl-licence.md) |

---

## 7. Modules

| Composant | Responsabilité |
|---|---|
| EdgeProxy (Caddy) | Point d’entrée unique, TLS interne, en-têtes de sécurité |
| AgentClient (Element Web) | Client, chiffrement et vérification des appareils |
| MessageServer (Synapse) | Transport, stockage chiffré, rétention |
| IdentityProvider (Keycloak) | Authentification, TOTP, rôles |
| AdminService (FastAPI) | Enrôlement, révocation, salles classifiées, annuaire |
| AuditLedger | Journal d’audit en ajout seul |
| Store (PostgreSQL) | Trois bases isolées |

Responsables et dépendances : [architecture/README.md](docs/architecture/README.md).

---

## 8. Structure du dépôt

```text
msgsov/
├── docker-compose.yml          # à créer au bloc 1
├── .env.example
├── caddy/Caddyfile
├── synapse/homeserver.yaml
├── keycloak/realm-export.json  # royaume préconfiguré, comptes fictifs
├── element/config.json
├── admin-api/                  # FastAPI, migrations SQL, tests pytest
├── docs/                       # documentation de référence (ce dossier)
├── README.md  LICENSE  SECURITY.md  CONTRIBUTING.md  CHANGELOG.md
└── PROJECT_OVERVIEW.md
```

---

## 9. Modèle de données principal

La base `adminapi` contient `ministeres`, `agents`, `niveaux_classification`, `salles` et `audit_log`. Synapse et Keycloak gèrent leurs propres tables. Détails : [data-dictionary.md](docs/data/data-dictionary.md).

---

## 10. Sécurité

Le socle de sécurité est obligatoire : chiffrement de bout en bout avec un protocole existant, hébergement souverain, identité vérifiée avec second facteur, révocation immédiate, minimisation des métadonnées. Les garanties sont formulées comme invariants dans [system-contract.md](docs/architecture/system-contract.md). La note de sécurité est dans [securite.md](docs/securite.md).

---

## 11. Stratégie de tests

- Tests unitaires du service d’administration (rôles, séquences de révocation avec simulations).
- Tests d’intégration contre l’installation locale (intrus, révocation, aucun clair en base, ports internes fermés).
- Scénarios de démonstration correspondant aux épreuves du jury.
- Vérifications manuelles sur téléphone.

Voir [testing/README.md](docs/testing/README.md).

---

## 12. Critères de réussite

- Les épreuves « serveur aveugle », « révocation », « intrus » et « innovation » passent en direct.
- `docker compose up` démarre l’ensemble sur une machine propre.
- Les tests de sécurité réussissent.
- Chaque membre explique l’enrôlement, la révocation et le lien Keycloak–Synapse.
- Le dossier de candidature est déposé dans les délais.

---

## 13. Décisions techniques principales

Voir l’[index des ADRs](docs/adr/README.md). Éléments structurants : Matrix plutôt que XMPP, Signal ou MLS ; Keycloak pour l’identité plutôt qu’une authentification maison ; client web plutôt qu’applications natives ; salles classifiées créées par un compte de service.

---

## 14. Résumé

Oryma assemble des briques open source pour fournir une messagerie chiffrée de bout en bout, hébergée par l’État, avec enrôlement contrôlé, révocation immédiate et salles à expiration. L’équipe n’écrit que le service d’administration et la configuration, et documente honnêtement les limites.
