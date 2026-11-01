# Guide de développement à deux

## Objectif

Ce guide organise le travail quotidien de deux membres dans un même dépôt, en un sprint très court, sans se bloquer ni se contredire. Les noms des membres sont à renseigner :

| Membre | Nom | Parcours |
|---|---|---|
| A | _[nom à compléter]_ | Infrastructure et identité |
| B | _[nom à compléter]_ | Service d’administration et produit |

## Sources de vérité

| Sujet | Source |
|---|---|
| Périmètre | [PRD](../product/product-requirements.md) |
| Comportement testable | [SRS](../product/software-requirements.md) |
| Garanties | [Contrat système](../architecture/system-contract.md) |
| Propriété des garanties | [Traçabilité](../architecture/requirements-traceability.md) |
| Contrats HTTP | [Registre API](../api/README.md) |
| Données | [Dictionnaire](../data/data-dictionary.md) |
| Installation | [Déploiement](../deployment/README.md) |
| Décisions | [ADRs](../adr/README.md) |

## Statuts d’un contrat

```text
PROPOSÉ → ACCEPTÉ → IMPLÉMENTÉ → VÉRIFIÉ
```

Un contrat Vérifié a une preuve exécutable (test ou démonstration). Un contrat ne passe pas à Accepté sans l’accord de son consommateur.

## Protocole de changement partagé

1. Annoncer le changement à l’autre membre.
2. Modifier le contrat et la documentation dans la même pull request.
3. Faire accepter par le consommateur.
4. Mettre à jour les tests et fixtures.
5. Passer le statut.

## Points de passage entre les deux parcours

| Quand | De → À | Contenu |
|---|---|---|
| Fin du bloc 1 | A → B | Compose démarre, Synapse et Keycloak accessibles, comptes de service |
| Fin du bloc 2 | A → B | Royaume Keycloak avec clients et rôles |
| Fin du bloc 3 | B → A | `POST /agents` et révocation prêts pour le test à deux appareils |
| Fin du bloc 4 | B → A | Salles classifiées et `DEMO_RETENTION` |

## Définition de prêt

Un changement est prêt pour la fusion lorsque le comportement attendu est implémenté, les tests pertinents passent, `docker compose up` démarre, la documentation est cohérente, aucun secret n’est présent et l’autre membre a relu et compris le changement.

## Plan du sprint

Le plan suppose environ 15 heures de travail effectif. Les durées sont indicatives : le point à surveiller est le **point de contrôle** de chaque bloc. **L’heure limite du dépôt est à confirmer** auprès du point focal du MTDPCE ; si elle est plus proche que le plan, appliquer l’ordre de sacrifice ci-dessous.

| Bloc | Durée | Membre A | Membre B | Point de contrôle |
|---|---|---|---|---|
| 0. Démarrage (ensemble) | 30 min | Vérifier Docker et la mémoire ; adresse unique et machine de démonstration | Dépôt public, licence AGPL-3.0, `.gitignore`, README minimal | Premier commit poussé |
| 1. Socle | 2 h | `docker-compose.yml` : PostgreSQL (trois bases), Caddy en TLS interne, Synapse, Element ; réseau interne | Schéma SQL, squelette FastAPI avec `/health`, clients Keycloak et Synapse, pytest installé | Element s’ouvre en HTTPS local, Synapse démarre |
| 2. Identité | 2 à 3 h | Keycloak (royaume préconfiguré, rôles, TOTP), connexion OIDC avec Synapse, inscription et mot de passe local coupés | `POST /agents`, jeton et rôle, audit, comptes de démonstration | Un agent enrôlé se connecte avec TOTP et échange un message chiffré ; un compte inconnu est rejeté |
| 3. Révocation | 2 h | Test à deux appareils ; réglages de métadonnées | `POST /agents/{id}/revoke`, échecs partiels, écran de confirmation | Révocation en direct pendant une conversation de groupe |
| 4. Innovation | 2 h | Rétention Synapse, purge courte pour la démonstration | `POST /rooms`, console (A1, A4, A5) | Un message d’une salle « Confidentiel » expire |
| 5. Fiabilité et tests | 1 h 30 | `healthcheck`, redémarrage, secrets, installation de zéro | Quatre tests de sécurité | `docker compose up` de zéro et tests verts |
| 6. Dossier | 2 h | Note de sécurité, répétition des épreuves | README, note de pré-projet, fiche équipe, attestations, script vidéo | Dossier complet en brouillon |
| 7. Vidéo et dépôt | 1 h 30 | Enregistrement de la vidéo avec B | Dépôt des cinq pièces, vérification du dépôt public | **Dépôt avec au moins 3 heures de marge** |

À faire au bloc 4 en premier : le test de 30 minutes de création de salle ([ADR-008](../adr/008-classified-rooms-service-account.md)).

### Ordre de sacrifice

On coupe dans cet ordre, du moins important au plus important :

1. Traduction en langue nationale (+3 points seulement).
2. Console d’administration en page dédiée : on garde l’API, appelée avec `curl` ou une page minimale.
3. Expiration automatique en direct : on la documente avec sa configuration.
4. Classification des salles.

On ne coupe **jamais** : chiffrement de bout en bout, enrôlement avec TOTP, révocation, rejet de l’intrus, installation en une commande, journal d’audit, note de sécurité, vidéo et dépôt.

### Points de décision

| Quand | Si… | Alors… |
|---|---|---|
| Fin du bloc 2 | La connexion OIDC Synapse–Keycloak ne fonctionne pas après 3 h | Chercher de l’aide (documentation officielle) avant de changer d’outil ; Authelia en dernier recours |
| Fin du bloc 3 | La révocation ne coupe pas la lecture des nouveaux messages | Vérifier le renouvellement des clés avec deux appareils ; documenter honnêtement |
| Fin du bloc 4 | La création de salle par le service dépasse 1 h | Plan B de l’ADR-008 |
| 3 h avant l’échéance | Une fonctionnalité n’est pas stable | La retirer de la vidéo et du dépôt |

## Décisions arrêtées

| Sujet | Décision | Quand |
|---|---|---|
| Innovation | Classification et expiration par salle | Fixé |
| Nom | **Oryma** ; `msgsov` reste l’identifiant technique historique à migrer progressivement | Fixé le 1er novembre 2026 |
| Adresse unique | `messagerie.local` si le téléphone la résout, sinon IP fixe | Bloc 0 |
| Machine de démonstration | Le PC le plus puissant (au moins 4 Go libres) | Bloc 0 |
| Licence | AGPL-3.0 | Fixé |
| Dépôt | GitHub, ou Codeberg si un compte existe | Bloc 0 |
| Langue nationale | Seulement si un locuteur peut relire ; en dernier | Bloc 4 |
| Annuaire, WebAuthn | Coupés | Fixé |
| Versions | Dernière stable publiée depuis plus de deux semaines, licence vérifiée | Bloc 1 |
| Comptes de démonstration | 1 administrateur, 3 agents, 1 intrus | Bloc 2 |
| Durées | Confidentiel 24 h, Diffusion restreinte 7 jours ; durées courtes via `DEMO_RETENTION` | Bloc 4 |
| Documentation du dépôt | README (2 pages) et `docs/securite.md` ; pas tout le dossier interne | Bloc 6 |

## Routine quotidienne

### Avant de commencer

Récupérer `main`, intégrer ses changements, vérifier que `docker compose up` démarre.

### Pendant le travail

Un commit par sous-tâche avec un message clair. **Ne jamais falsifier les dates.** Annoncer les fichiers sensibles.

### Avant la transmission

Tests, lint, relecture du diff, vérification d’absence de secret, mise à jour de la documentation et du changelog.

## Règles anti-friction

- Une branche par membre ; fusions aux points de contrôle.
- Aucun secret dans le dépôt : vérifier avant chaque envoi.
- Relecture croisée à la fin des blocs 3 et 5 : chacun explique à l’autre son composant, comme devant le jury.
- Prévoir du sommeil et geler le code 3 heures avant l’échéance : une erreur de configuration à 4 h du matin coûte plus cher qu’une heure de repos.

## Questions probables du jury

| Question | Qui doit savoir répondre |
|---|---|
| Pourquoi le serveur ne peut-il pas lire les messages ? Où se fait le chiffrement ? | Les deux |
| Que se passe-t-il exactement lors d’une révocation, étape par étape ? | Les deux |
| Comment Synapse sait-il qu’un utilisateur a bien passé le TOTP ? | Les deux |
| Comment le rôle `admin` est-il vérifié dans le service FastAPI ? | Les deux |
| Que voit le serveur malgré le chiffrement ? | Les deux |
| Quelles sont les limites connues ? | Les deux |
| Pourquoi aucune cryptographie n’a-t-elle été écrite par l’équipe ? | Les deux |

## Limites actuelles

Cette documentation décrit la cible du prototype avant initialisation du code. Les commandes, durées et mesures devront être mises à jour avec des preuves au fur et à mesure de l’implémentation. L’heure limite du dépôt et les noms des membres restent à renseigner.
