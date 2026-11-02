# msgsov — Software Requirements Specification

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>product/product-requirements.md</code></p>

## Vocabulaire normatif

- **DOIT / MUST** : exigence absolue ; sa violation rend le système non conforme.
- **DEVRAIT / SHOULD** : exigence forte ; toute dérogation doit être justifiée et documentée.
- **PEUT / MAY** : capacité facultative.

## Définitions

| Terme | Définition |
|---|---|
| E2EE | Chiffrement de bout en bout : seuls les appareils des participants peuvent lire un message |
| Olm / Megolm | Mécanismes de chiffrement de Matrix : Olm entre deux appareils, Megolm pour les salles de groupe |
| OIDC / SSO | Protocole par lequel Synapse et la console délèguent la connexion à Keycloak |
| TOTP | Code à usage unique à 6 chiffres, généré par une application d’authentification (second facteur) |
| Enrôlement | Création d’un compte agent par un administrateur |
| Révocation | Retrait immédiat de tous les accès d’un agent |
| Salle classifiée | Salle créée avec un niveau (Diffusion restreinte ou Confidentiel) et une durée de vie |

## Acteurs

| Acteur | Description |
|---|---|
| Agent | Agent enrôlé qui échange des messages et des fichiers |
| Administrateur | Agent avec le rôle `admin` : enrôle, révoque, consulte l’audit ; **ne lit pas les conversations** |
| Service d’administration | API FastAPI qui orchestre Keycloak et Synapse |
| Compte de service Synapse | Compte technique sans droits d’administration qui crée les salles classifiées |
| Jury | Observateur lors des épreuves en direct |

## Exigences fonctionnelles

### FR-010 — Identité et accès

- **FR-011** : Le système DOIT authentifier tout agent par SSO Keycloak avec mot de passe puis code TOTP.
- **FR-012** : Le système DOIT rejeter tout compte non enrôlé, à la connexion comme à l’invitation dans une salle.
- **FR-013** : Le système DOIT désactiver l’inscription publique, l’accès invité et le mot de passe local de Synapse.
- **FR-014** : Le système DOIT contrôler le rôle côté serveur pour chaque appel d’administration.

### FR-020 — Messagerie

- **FR-021** : Un agent DOIT pouvoir ouvrir une conversation à deux et créer ou rejoindre un groupe.
- **FR-022** : Un agent DOIT pouvoir envoyer et recevoir des messages texte dans une salle.
- **FR-023** : Un agent DOIT pouvoir envoyer et télécharger des fichiers dans une salle.
- **FR-024** : Toute salle DOIT être chiffrée de bout en bout dès sa création.

### FR-030 — Administration

- **FR-031** : Un administrateur DOIT pouvoir enrôler un agent (nom, ministère, fonction, rôle).
- **FR-032** : Un administrateur DOIT pouvoir révoquer un agent ; l’effet DOIT être immédiat sur tous ses appareils.
- **FR-033** : Chaque enrôlement, révocation, changement de rôle et création de salle DOIT être inscrit dans un journal d’audit consultable par les administrateurs.
- **FR-034** : Un administrateur DOIT pouvoir changer le rôle d’un agent.
- **FR-035** : Le service d’administration DOIT exposer un point de contrôle d’état `/health`.

### FR-040 — Classification et expiration

- **FR-041** : Un agent DOIT pouvoir créer, depuis la console (écran A5), une salle avec un niveau de classification.
- **FR-042** : Les messages d’une salle classifiée DEVRAIENT être purgés du serveur à l’échéance du niveau.
- **FR-043** : Le niveau DOIT figurer dans le nom de la salle et dans la liste « Mes salles » de la console.
- **FR-044** : Le service DOIT refuser la création si l’agent demandeur ou un membre n’est pas un agent actif.

La classification s’applique à la **salle**, pas au message individuel : tous les messages d’une salle classifiée héritent de sa durée de vie. La classification message par message est une piste d’évolution.

### FR-050 — Interface et compatibilité

- **FR-051** : Le client DOIT être utilisable sur ordinateur et sur téléphone avec le même compte et la même adresse, et DEVRAIT pouvoir être installé sur l’écran d’accueil.
- **FR-052** : L’interface PEUT être proposée en moré ou en dioula en plus du français.
- **FR-053** : La console d’administration DEVRAIT être utilisable sur téléphone.

### FR-060 — Déploiement

- **FR-061** : Le système DOIT s’installer sur une machine propre en une commande, sans service tiers.
- **FR-062** : Les comptes de démonstration fictifs DOIVENT être créés automatiquement par le royaume Keycloak préconfiguré.

## Règles métier

| ID | Règle |
|---|---|
| BR-001 | Un agent n’existe que s’il a été enrôlé par un administrateur. |
| BR-002 | Un administrateur gère les accès ; il ne peut pas lire les conversations. |
| BR-003 | Valeurs par défaut : Diffusion restreinte, 7 jours ; Confidentiel, 24 heures. `DEMO_RETENTION=true` applique respectivement 5 minutes et 2 minutes aux nouvelles salles. |
| BR-004 | Dans le prototype, une révocation est définitive ; un retour passe par un nouvel enrôlement. |
| BR-005 | Les données de développement et de démonstration sont exclusivement fictives. |
| BR-006 | Le service d’administration ne poste aucun message dans une salle chiffrée. |

## Contraintes non fonctionnelles

### Performance

- **NFR-P01** : L’envoi et la réception d’un message DEVRAIENT prendre moins de 2 secondes sur le réseau local de démonstration.

### Disponibilité et résilience

- **NFR-A01** : Les conteneurs DOIVENT redémarrer automatiquement et exposer un contrôle d’état.
- **NFR-A02** : Une étape de révocation en échec DOIT être signalée à l’administrateur ; elle NE DOIT PAS être masquée.

### Sécurité et confidentialité

- **NFR-S01** : Les communications DOIVENT utiliser TLS ; TLS 1.3 DEVRAIT être privilégié.
- **NFR-S02** : Aucun secret ni clé privée NE DOIT figurer dans le dépôt.
- **NFR-S03** : Les adresses IP et journaux d’accès DOIVENT être conservés le moins possible.
- **NFR-S04** : Les images et dépendances DOIVENT être figées à une version précise.
- **NFR-S05** : Aucun compte ni donnée réelle NE DOIT être présent dans Git, les tests ou les démonstrations.

### Utilisabilité et compatibilité

- **NFR-U01** : L’application DOIT fonctionner sur ordinateur et téléphone avec les navigateurs récents.
- **NFR-U02** : Un agent DEVRAIT envoyer son premier message en moins de 3 minutes après sa première connexion, sans formation.
- **NFR-U03** : L’interface DOIT offrir des contrastes suffisants, une navigation au clavier et ne jamais porter une information par la couleur seule.

### Portabilité et maintenance

- **NFR-M01** : `docker compose up` DOIT démarrer l’ensemble sans autre action, sur une machine propre.
- **NFR-M02** : Aucun service tiers (API, CDN, polices distantes) NE DOIT être nécessaire au fonctionnement.
- **NFR-M03** : Les contrats HTTP DOIVENT être publiés sous forme OpenAPI.
- **NFR-M04** : Le dépôt DOIT être sous licence OSI avec chaque composant cité avec sa licence et son lien.
- **NFR-M05** : Toute modification d’un contrat, d’un invariant ou d’une décision DOIT mettre à jour la documentation liée.

## Cas d’erreur

| ID | Déclencheur | Comportement requis |
|---|---|---|
| ERR-011 | Compte non enrôlé à la connexion | Refuser avec le message « Ce compte n’est pas autorisé sur cette messagerie. » |
| ERR-012 | Code TOTP erroné | Refuser, expliquer, limiter les essais (blocage temporaire par Keycloak) |
| ERR-013 | Jeton absent, invalide ou expiré | Retourner HTTP 401 |
| ERR-014 | Rôle insuffisant | Retourner HTTP 403 et inscrire la tentative à l’audit |
| ERR-021 | Ministère introuvable lors de l’enrôlement | Retourner HTTP 404 |
| ERR-022 | Identifiant déjà utilisé lors de l’enrôlement | Retourner HTTP 409 |
| ERR-023 | Corps de requête invalide | Retourner HTTP 422 avec les seuls noms de champs et types d’erreur ; ne pas refléter les valeurs reçues |
| ERR-031 | Agent introuvable | Retourner HTTP 404 |
| ERR-032 | Révocation d’un agent déjà révoqué | Retourner HTTP 200 avec l’état existant, sans effet de bord |
| ERR-033 | Étape de révocation en échec | Retourner HTTP 502 avec le détail des étapes, conserver les étapes réussies, permettre de réessayer sans répéter leurs effets |
| ERR-034 | Révocation du même agent déjà en cours | Retourner HTTP 409 ; l’appelant peut réessayer après la fin de l’opération |
| ERR-041 | Niveau de classification inconnu | Retourner HTTP 422 |
| ERR-042 | Membre ou demandeur non agent actif | Retourner HTTP 422 sans créer de salle |
| ERR-043 | Création de salle impossible (compte de service, Synapse) | Retourner une erreur corrélée ; ne pas enregistrer de salle partielle |
| ERR-500 | Dépendance interne indisponible | Retourner une erreur corrélée sans exposer de secret |
