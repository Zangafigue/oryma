# Contribuer à Oryma

Ce guide définit une méthode de travail adaptée à une équipe de deux personnes construisant le prototype dans un même dépôt, en un sprint très court.

L’organisation retenue repose sur :

- une branche `main` pour les versions stables et démontrables ;
- une branche de travail par membre (`dev/a-infra-identite` et `dev/b-admin-produit`) ;
- des fusions vers `main` à chaque point de contrôle du plan, après vérification que `docker compose up` démarre toujours.

Pour une décision structurante, consultez les [ADRs](docs/adr/README.md). Pour le travail quotidien, utilisez le [guide de développement à deux](docs/development/README.md). Les contrats partagés sont indexés dans :

- le [registre API](docs/api/README.md) ;
- le [dictionnaire de données](docs/data/data-dictionary.md) ;
- le [guide de déploiement](docs/deployment/README.md) ;
- l’[index des limites d’architecture](docs/architecture/README.md) ;
- la [stratégie de tests](docs/testing/README.md) ;
- le [scénario de démonstration](docs/demo/mvp-scenario.md).

Une modification du périmètre, d’un invariant, d’un contrat API, du modèle de données ou de la stack doit mettre à jour la documentation concernée.

---

## Organisation des branches

```text
main
  ├── dev/a-infra-identite
  └── dev/b-admin-produit
```

`main` contient uniquement une version stable, testée et démontrable. Le développement quotidien ne se fait pas directement dessus.

### Membre A — Infrastructure et identité

Docker Compose, Caddy, PostgreSQL, Synapse, Keycloak (royaume préconfiguré, SSO, TOTP), durcissement, rétention, note de sécurité.

Fichiers principaux : `docker-compose.yml`, `caddy/`, `synapse/`, `keycloak/`, `.env.example`, `docs/securite.md`.

### Membre B — Service d’administration et produit

FastAPI, schéma `adminapi`, console d’administration, création de salles classifiées, thème et textes d’Element, tests pytest, README et note de pré-projet.

Fichiers principaux : `admin-api/`, `element/`, `docs/`.

### Pourquoi cette répartition ?

Elle sépare ce qui dépend du réseau et des conteneurs de ce qui dépend du code applicatif, avec peu de fichiers modifiés par les deux. Les points de passage sont décrits dans le guide de développement. **Chacun doit pouvoir expliquer la partie de l’autre** : le jury désigne la personne qui répond.

Les noms des membres A et B sont à renseigner dans [docs/development/README.md](docs/development/README.md).

---

## Fichiers sensibles et conflits

À annoncer avant modification :

- `docker-compose.yml` et `.env.example` (A, annonce à B) ;
- `synapse/homeserver.yaml` et `keycloak/realm-export.json` (A, annonce à B) ;
- `admin-api/migrations/` et le contrat d’API (B, annonce à A) ;
- `docs/api/`, `docs/data/` et `docs/architecture/system-contract.md` (changement partagé : voir le protocole du guide de développement).

## Synchronisation

Avant chaque fusion vers `main` : récupérer `main`, intégrer ses changements dans sa branche, relancer `docker compose up` et les tests. En cas de conflit, ne résolvez pas à l’aveugle un fichier de configuration : parlez-en à son propriétaire.

## Pull requests

Une pull request par intention cohérente, avec le modèle fourni. Elle décrit l’intention, les commandes de vérification, les impacts (sécurité, métadonnées, API, déploiement) et le retour arrière.

## Commits

Les messages suivent le format Conventional Commits :

```text
<type>: <description concise>
```

Types : `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `security`, `merge`.

Exemples :

```text
docs: add system contract and invariants
feat: add agent enrollment endpoint
feat: revoke agent across keycloak and synapse
test: add intruder rejection scenario
security: disable guest access and federation
```

Un commit représente une intention compréhensible. Ne placez pas tout le travail dans un commit final : **l’historique doit montrer une progression réelle sur la durée du sprint**. **Ne falsifiez jamais les dates des commits.**

## Standards de développement

### Principes communs

- Préserver les invariants de [system-contract.md](docs/architecture/system-contract.md).
- **Aucune cryptographie écrite par l’équipe** : utiliser uniquement Matrix.
- Garder la logique métier indépendante des routes HTTP.
- Préférer des types explicites, des fonctions courtes et des noms métier ; commenter le **pourquoi**.
- Ne jamais laisser de secret, de clé privée ni de journal contenant un message.
- Aucun échec silencieux : une erreur acceptée est visible et corrélable.
- Utiliser uniquement des comptes et données fictifs.

### Backend (admin-api)

- Formatter et linter avec Ruff ; typage Python ; tests avec pytest.
- Vérifier le jeton et le rôle dans une dépendance commune, jamais route par route à la main.
- Chaque étape de révocation est rejouable et son résultat est visible.

### Configuration et conteneurs

- Images figées à une version précise ; jamais `latest`.
- Seul Caddy publie un port.
- `restart: unless-stopped` et `healthcheck` sur chaque service ; `no-new-privileges` et `cap_drop: ALL` quand c’est possible.
- Les secrets viennent de `.env` ou de secrets Docker, jamais du dépôt.

## Tests et vérifications

Avant chaque pull request : tests pertinents, lint, démarrage complet. Avant chaque fusion vers `main` : le [scénario de démonstration](docs/demo/mvp-scenario.md) concerné. Voir la [stratégie de tests](docs/testing/README.md).

## Documentation et ADRs

Toute décision structurante crée un ADR ; ne supprimez pas un ADR accepté. Une modification de contrat met à jour la documentation dans la même pull request. Mettez à jour le [CHANGELOG](CHANGELOG.md).

## Gestion des conflits de conception

Un désaccord sur un contrat partagé se règle avant d’écrire du code : le propriétaire propose, le consommateur accepte ou conteste dans le registre, et la décision est consignée (ADR si structurante).

## Définition de terminé

Un bloc est terminé lorsque :

- le comportement attendu est implémenté ;
- les tests pertinents passent ;
- `docker compose up` démarre l’ensemble ;
- les erreurs importantes sont traitées ;
- la documentation est cohérente ;
- aucun secret ni clé privée n’est présent ;
- la branche a intégré la dernière version de `main` ;
- le résultat fonctionnel a été vérifié par l’autre membre ;
- la pull request est fusionnée.

Une version est prête pour le dépôt du dossier lorsque les épreuves du jury passent en démonstration, que les tests passent, que l’installation de zéro fonctionne et que chaque membre sait expliquer le socle de sécurité.
