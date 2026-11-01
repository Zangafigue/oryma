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
| `DEMO_RETENTION` | Active les durées d’expiration courtes pour la démonstration |

## Installation (cible)

```bash
cp .env.example .env     # puis générer les secrets via le script prévu
docker compose up -d
```

À vérifier après installation : tous les services sont `healthy`, Element s’ouvre en HTTPS, la connexion SSO avec TOTP fonctionne avec un compte de démonstration.

Au démarrage, `admin-api` applique les migrations SQL numérotées avant de lancer FastAPI. Une migration en échec empêche le service de démarrer et reste visible dans ses journaux.

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
