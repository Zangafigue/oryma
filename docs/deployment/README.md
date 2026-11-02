# Guide de déploiement

Ce dossier remplace le « guide des connecteurs » de la documentation d’origine : msgsov n’a pas de connecteurs, mais son installation, son certificat interne et son usage sur téléphone sont les points les plus délicats.

Toutes les commandes ci-dessous sont des **cibles** à valider sur une installation propre au bloc correspondant.

## Objectif

Installer l’ensemble en une commande sur une infrastructure maîtrisée, sans service tiers, et l’utiliser depuis un PC et un téléphone Android.

## Prérequis

- Linux avec Docker et Docker Compose.
- 4 Go de RAM disponibles (2 Go au minimum à cause de Keycloak).
- Accès Internet **uniquement** pour télécharger les images à l’installation.
- Un PC héberge ; l’autre PC et le téléphone sont des clients du même réseau.

## Adresse unique

Le PC et le téléphone utilisent **exactement la même adresse** pour joindre Element, Synapse et Keycloak. Si elles diffèrent, la connexion OIDC échoue. Elle sert aussi de nom de serveur Matrix, qu’on ne peut plus changer après le premier démarrage sans tout recréer.

Choix à faire au bloc 0, après un test de 5 minutes :

1. `messagerie.local`, si le téléphone Android la résout ;
2. sinon une adresse IP fixe, avec le point d’accès Wi-Fi partagé par le PC hôte.

Caddy sait émettre un certificat interne pour un nom comme pour une IP.

## Variables d’environnement (cible)

`.env.example` liste les noms ; les valeurs sensibles sont générées au premier lancement et ne sont jamais committées.

| Variable | Rôle |
|---|---|
| `MSGSOV_HOST` | Adresse unique (nom ou IP) |
| `POSTGRES_PASSWORD` | Compte administrateur PostgreSQL |
| `SYNAPSE_DB_PASSWORD`, `KEYCLOAK_DB_PASSWORD`, `ADMINAPI_DB_PASSWORD` | Un compte par base |
| `SYNAPSE_REGISTRATION_SECRET` | Création des comptes de service Synapse |
| `KEYCLOAK_ADMIN_PASSWORD` | Compte d’administration Keycloak (console non exposée) |
| `OIDC_SYNAPSE_SECRET` | Secret du client `synapse` |
| `DEMO_RETENTION` | `true` applique 5 min (Diffusion restreinte) et 2 min (Confidentiel), sinon 7 jours et 24 h |
| `SYNAPSE_ADMIN_ACCESS_TOKEN` | Jeton du compte Synapse dédié à la révocation des agents |
| `SYNAPSE_ROOM_SERVICE_MATRIX_ID` | Identifiant du compte Matrix non administrateur qui crée les salles |
| `SYNAPSE_ROOM_SERVICE_ACCESS_TOKEN` | Jeton de ce compte de service, réservé à la création des salles |
| `ORYMA_ENVIRONMENT` | `development` uniquement pour déclarer un environnement de développement ; Compose utilise `production` par défaut |
| `ORYMA_ENABLE_LOCAL_BOOTSTRAP` | `true` uniquement pour initialiser explicitement une base locale de développement |
| `ORYMA_ENABLE_LOCAL_OIDC_HARNESS` | `true` uniquement pour servir le harnais PKCE temporaire en développement |

Le compte Synapse utilisé pour la révocation doit être distinct du compte de service des salles. L’API Admin Synapse nécessite un compte administrateur du homeserver ; réservez-le à `admin-api`, provisionnez son jeton hors du dépôt, puis renseignez `SYNAPSE_ADMIN_ACCESS_TOKEN` dans `.env` et redémarrez `admin-api`. Sans ce jeton, l’API démarre mais les étapes Synapse d’une révocation échouent explicitement. Ne placez jamais le jeton dans un fichier versionné, une commande conservée dans l’historique ou les journaux.

Le compte des salles doit rester un utilisateur Matrix ordinaire, sans droits d’administration Synapse. Créez-le comme compte non administrateur avec le mécanisme d’inscription partagée Synapse, puis stockez son identifiant et son jeton dans les deux variables correspondantes de `.env`. Il ne doit pas recevoir de rôle d’administration ; l’API l’utilise uniquement pour créer une salle chiffrée, inviter les membres et quitter la salle. La suppression compensatoire d’une salle incomplète utilise séparément le jeton administrateur Synapse.

`DEMO_RETENTION=true` raccourcit les durées appliquées aux nouvelles salles à 300 secondes (Diffusion restreinte) et 120 secondes (Confidentiel). L’instantané persisté dans `salles.duree_vie_secondes` correspond toujours à la durée réellement envoyée à Synapse. Laisser cette option désactivée hors démonstration ; les salles existantes ne sont pas modifiées.

## Installation (cible)

```bash
cp .env.example .env     # puis générer les secrets via le script prévu
docker compose up -d
```

À vérifier après installation : tous les services sont `healthy`, Element s’ouvre en HTTPS, la connexion SSO avec TOTP fonctionne avec un compte de démonstration.

Au démarrage, `admin-api` applique les migrations SQL numérotées avant de lancer FastAPI. Une migration en échec empêche le service de démarrer et reste visible dans ses journaux.

## Bootstrap initial local (développement uniquement)

Les migrations ne créent aucun ministère ni administrateur. Pour initialiser une base **locale de développement**, connectez d’abord l’utilisateur fictif à Keycloak et récupérez son UUID Keycloak ainsi que son identifiant Matrix. La commande exige une confirmation explicite et reçoit ses deux garde-fous uniquement pour cette exécution :

```bash
docker compose up -d --build admin-api
docker compose exec \
  -e ORYMA_ENVIRONMENT=development \
  -e ORYMA_ENABLE_LOCAL_BOOTSTRAP=true \
  admin-api admin-api-bootstrap-local \
  --confirm-local \
  --keycloak-id UUID_KEYCLOAK \
  --matrix-id '@utilisateur:oryma.local' \
  --admin-name 'Administrateur de démonstration'
```

La commande crée le ministère fictif `DEV-DEMO` et un premier admin actif lié aux identifiants fournis, dans une transaction. Elle est idempotente pour les mêmes valeurs ; elle refuse les identifiants déjà attribués, une configuration existante incompatible ou la présence d’un autre admin actif. Elle inscrit l’action dans `audit_log`. Aucun mot de passe ni jeton n’est demandé ou enregistré par cette commande.

La commande refuse par défaut les environnements autres que `development`. Elle n’expose aucune route API et n’est pas un mécanisme d’initialisation de production : ne l’exécutez jamais sur une base partagée ou de production. L’UUID Keycloak peut être lu dans la fiche de l’utilisateur Keycloak ; l’identifiant Matrix doit correspondre au compte Matrix réellement provisionné.

## Vérification OIDC locale (harnais temporaire)

Le harnais n’est pas la console produit. Il est servi uniquement si `ORYMA_ENVIRONMENT=development` et `ORYMA_ENABLE_LOCAL_OIDC_HARNESS=true` sont définis dans le `.env` local ignoré par Git. Il réalise Authorization Code + PKCE S256 pour le client public `console`, affiche les claims utiles sans conserver l’access token après fermeture/rechargement de l’onglet, puis permet de tester l’appel authentifié à `POST /api/v1/agents`.

```bash
# Dans .env local uniquement :
ORYMA_ENVIRONMENT=development
ORYMA_ENABLE_LOCAL_OIDC_HARNESS=true

docker compose up -d --build admin-api caddy
```

Ouvrir `https://${ORYMA_HOST}/admin/`, se connecter avec le compte administrateur de démonstration, vérifier `azp=console`, `aud` contenant `admin-api` et le rôle realm `admin`, puis tester l’enrôlement avec un identifiant fictif et le ministère `DEV-DEMO`. L’API reste l’autorité de validation du jeton. La réponse peut inclure le mot de passe temporaire du nouvel agent : le transmettre uniquement par le canal convenu et ne pas le copier dans les journaux ou un ticket. Après le test, remettre `ORYMA_ENABLE_LOCAL_OIDC_HARNESS=false` et `ORYMA_ENVIRONMENT=production`, puis redéployer `admin-api` et `caddy`. Ne jamais activer ce harnais sur une instance partagée ou de production.

## Réseaux, volumes et secrets

- Réseau `externe` : Caddy seulement. Réseau `interne` sans accès sortant : tous les autres services.
- Volumes nommés : données PostgreSQL, médias de Synapse, données de Caddy (dont l’autorité de certification).
- `restart: unless-stopped` et `healthcheck` sur chaque service ; `no-new-privileges` et `cap_drop: ALL` quand c’est possible.
- La console d’administration de Keycloak n’est pas routée par Caddy.
- Comptes de service Synapse : créés avec le secret d’enregistrement ; jetons stockés comme secrets Docker (à vérifier à l’installation).

## Certificat interne et téléphone Android

Le certificat généré par Caddy n’est pas reconnu par défaut par les téléphones. Il faut installer l’**autorité racine** de Caddy sur chaque appareil de démonstration.

### 1. Récupérer le certificat racine

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./root.crt
```

Le chemin peut varier selon la version de l’image : le vérifier avec `docker compose exec caddy ls /data/caddy/pki/authorities/local/`.

**N’envoyez jamais `root.key`**, la clé privée de l’autorité, qui est dans le même dossier : elle reste sur le serveur, ni dans Git ni sur le téléphone.

### 2. Transférer `root.crt`

Câble USB, partage local ou carte SD. Évitez les services en ligne.

### 3. L’installer sur Android

Les menus varient selon la marque :

**Paramètres → Sécurité → Plus de paramètres de sécurité → Chiffrement et identifiants → Installer un certificat → Certificat CA**

Un verrouillage d’écran doit être activé. Android affiche ensuite une notification permanente de « réseau potentiellement surveillé » : c’est normal.

### 4. Vérifier avec Chrome

Ouvrir l’adresse unique : le cadenas doit apparaître. Puis menu → **Installer l’application** (ou « Ajouter à l’écran d’accueil »). Chrome est recommandé pour la démonstration ; Firefox pour Android gère les autorités ajoutées par l’utilisateur différemment.

### Pièges

1. **Une seule adresse** pour tous les appareils (voir plus haut).
2. **Ne détruisez pas le volume de Caddy** après l’installation sur le téléphone : `docker compose down -v` efface l’autorité, Caddy en génère une nouvelle et le téléphone doit tout réinstaller. Faites le test « installation depuis zéro » **avant** d’installer le certificat pour la démonstration finale.
3. Les applications natives Element peuvent refuser les autorités ajoutées par l’utilisateur : c’est une raison de viser le web ([ADR-009](../adr/009-installable-web-client.md)).

Après la démonstration, le certificat peut être retiré : Paramètres → Sécurité → Identifiants de confiance, onglet « Utilisateur ».

## Versions des images

Ne pas figer de mémoire. Au bloc 1 : dernière version stable de chaque image publiée depuis plus de deux semaines, licence vérifiée, versions notées dans le README.

## Durcissement

- Seul Caddy publie un port ; PostgreSQL, Synapse, Keycloak et l’API restent internes.
- TLS 1.3, HSTS, CSP, `X-Frame-Options`, `Referrer-Policy: no-referrer`.
- Protection anti-force brute et durée de session courte dans Keycloak.
- Inscription, accès invité et mot de passe local de Synapse désactivés ; fédération coupée, port 8448 non exposé.
- Présence, aperçus d’URL coupés ; conservation courte des adresses IP.
- Détection de secrets avant chaque envoi (par exemple `gitleaks`) et analyse des images (par exemple `trivy`).

## Notifications et limites mobiles

Les notifications en arrière-plan passent normalement par un service tiers (Google ou Apple) : le prototype ne les garantit pas quand l’application est fermée.

## Critères d’acceptation

- [ ] `docker compose up` fonctionne sur une machine propre.
- [ ] Aucun port interne n’est joignable depuis l’extérieur.
- [ ] Le téléphone Android ouvre l’application sans avertissement de certificat.
- [ ] Aucun secret n’est présent dans le dépôt.
