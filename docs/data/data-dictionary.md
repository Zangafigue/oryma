# Dictionnaire de données msgsov

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>architecture/system-architecture.md</code></p>

## Rôle de ce document

Ce dictionnaire fixe les noms, types, énumérations, relations et propriétaires des données du service d’administration (base `adminapi`). Il est la référence des migrations SQL, de l’API et des fixtures.

Synapse et Keycloak gèrent leurs propres tables ; elles ne sont **pas** modélisées ici et le service d’administration n’y accède jamais directement.

## Conventions globales

### Nommage

- Tables et colonnes en `snake_case`, noms en français pour les notions métier (`agents`, `salles`, `ministeres`).
- Énumérations en minuscules sans accent (`actif`, `revoque`).
- Codes d’action d’audit en majuscules (`ENROLEMENT`).

### Types logiques

| Type logique | Type SQL |
|---|---|
| Identifiant | `UUID` (`gen_random_uuid()`), sauf `ministeres.id` (`SERIAL`) et `audit_log.id` (`BIGSERIAL`) |
| Texte | `TEXT` |
| Horodatage | `TIMESTAMPTZ`, valeur par défaut `now()` |
| Structure libre | `JSONB` |
| Durée | `INT` en secondes |

### Nullabilité et absence

Une colonne est `NOT NULL` sauf mention contraire. `revoque_le` et `revoque_par` sont nuls tant que l’agent est actif.

## Référentiel des enums

| Enum | Valeurs |
|---|---|
| `role_agent` | `admin`, `agent` |
| `statut_agent` | `actif`, `revoque` |
| `niveaux_classification.code` | `DIFFUSION_RESTREINTE`, `CONFIDENTIEL` |
| `audit_log.action` | `ENROLEMENT`, `REVOCATION`, `CHANGEMENT_ROLE`, `CREATION_SALLE`, `TENTATIVE_ACCES_REFUSE` |

## Schéma SQL de référence

```sql
CREATE TYPE role_agent   AS ENUM ('admin', 'agent');
CREATE TYPE statut_agent AS ENUM ('actif', 'revoque');

CREATE TABLE ministeres (
  id   SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  nom  TEXT NOT NULL
);

CREATE TABLE agents (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_id  UUID UNIQUE NOT NULL,
  matrix_id    TEXT UNIQUE NOT NULL,
  nom_complet  TEXT NOT NULL,
  ministere_id INT REFERENCES ministeres(id),
  fonction     TEXT,
  role         role_agent   NOT NULL DEFAULT 'agent',
  statut       statut_agent NOT NULL DEFAULT 'actif',
  cree_le      TIMESTAMPTZ NOT NULL DEFAULT now(),
  cree_par     UUID REFERENCES agents(id),
  revoque_le   TIMESTAMPTZ,
  revoque_par  UUID REFERENCES agents(id)
);

CREATE TABLE niveaux_classification (
  code               TEXT PRIMARY KEY,
  libelle            TEXT NOT NULL,
  duree_vie_secondes INT  NOT NULL,
  transfert_interdit BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE salles (
  room_id  TEXT PRIMARY KEY,
  nom      TEXT NOT NULL,
  niveau   TEXT REFERENCES niveaux_classification(code),
  cree_par UUID REFERENCES agents(id),
  cree_le  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id         BIGSERIAL PRIMARY KEY,
  acteur_id  UUID REFERENCES agents(id),
  action     TEXT NOT NULL,
  cible_id   UUID REFERENCES agents(id),
  details    JSONB,
  horodatage TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Entités

### `ministeres`

Référentiel fictif pour la démonstration (`MIN-DEMO-A`, `MIN-DEMO-B`). Propriétaire : EnrollmentService.

### `agents`

| Colonne | Description |
|---|---|
| `keycloak_id` | Identifiant de l’utilisateur dans Keycloak, unique |
| `matrix_id` | Identifiant Matrix (`@identifiant:<nom du serveur>`), unique |
| `role` | `admin` ou `agent` ; doit rester cohérent avec le rôle Keycloak |
| `statut` | `actif` ou `revoque` ; une révocation est définitive dans le prototype |
| `cree_par`, `revoque_par` | Agent administrateur auteur de l’action |

Aucun mot de passe ni code TOTP n’est stocké ici.

### `niveaux_classification`

Valeurs de départ : `DIFFUSION_RESTREINTE`, 7 jours (604 800 s) ; `CONFIDENTIEL`, 24 heures (86 400 s). `transfert_interdit` est **indicatif** : il décrit une règle d’usage affichée dans l’interface et n’empêche pas techniquement la copie d’un message par un destinataire. Pour la démonstration, une variable d’environnement ramène les durées à quelques minutes.

### `salles`

Une salle classifiée créée par le service. `niveau` est nul pour une salle ordinaire non enregistrée (non applicable, les salles ordinaires ne sont pas listées). Le niveau est aussi présent dans le nom de la salle côté Matrix.

### `audit_log`

Une ligne par action d’administration. `details` ne contient ni adresse IP, ni contenu de message, ni secret. Le compte de base du service a uniquement les droits d’insertion et de lecture sur cette table.

## Données visibles du serveur Matrix

Ce que Synapse connaît malgré le chiffrement est décrit dans [securite.md](../securite.md) (membres des salles, horaires, tailles, appareils, durée de rétention, noms de salles).

## Propriété des données

| Donnée | Propriétaire | Autres composants |
|---|---|---|
| Comptes, mots de passe, TOTP, rôles Keycloak | IdentityProvider | AdminService via API |
| Comptes Matrix, salles, événements chiffrés, appareils | MessageServer | AdminService via API |
| `agents`, `ministeres`, `salles`, `niveaux_classification` | AdminService | Console |
| `audit_log` | AuditLedger | Console (lecture) |

## Règles d’évolution

### Changement compatible

Ajout d’une colonne optionnelle ou d’une table. Migration SQL numérotée, appliquée à l’installation.

### Changement incompatible

Suppression ou renommage d’une colonne, changement de type : nouvelle migration avec transition, mise à jour de l’API et des tests dans la même pull request.

## Checklist avant migration

- [ ] Le dictionnaire et le schéma de référence sont mis à jour.
- [ ] La migration s’applique sur une installation propre et sur une base existante.
- [ ] L’API, les fixtures et les tests concernés sont à jour.
- [ ] Aucune donnée sensible n’est ajoutée sans décision.
- [ ] Le droit d’insertion seule sur `audit_log` est conservé.
