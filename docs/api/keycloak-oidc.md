# Contrat OIDC Keycloak — Oryma

Ce document verrouille le contrat consommé par Synapse, la console et l’API d’administration. Les valeurs concernent le prototype avec `ORYMA_HOST=oryma.local` ; une autre adresse doit être fixée **avant** le premier démarrage de Synapse et rendue dans le royaume au démarrage.

## Autorité et clés

| Élément | Valeur |
|---|---|
| Royaume | `oryma` |
| Issuer exact | `https://oryma.local/auth/realms/oryma` |
| Découverte OIDC | `https://oryma.local/auth/realms/oryma/.well-known/openid-configuration` |
| JWKS | `https://oryma.local/auth/realms/oryma/protocol/openid-connect/certs` |
| JWKS depuis l’API Docker | `http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs` |
| Algorithmes acceptés | clés publiques publiées par le JWKS ; aucun secret partagé pour valider un jeton utilisateur |

Synapse et l’API doivent vérifier l’issuer exact, l’expiration et la signature. L’API récupère régulièrement le JWKS et n’accepte aucun jeton non signé ou signé par une autre autorité.

Synapse conserve cet issuer public et utilise les endpoints OIDC HTTPS publiés par Caddy : Synapse exige HTTPS pour le `token_endpoint`. L’API d’administration utilise séparément son JWKS interne (`http://keycloak:8080/...`) pour éviter de dépendre du proxy pour la validation de ses jetons.

## Clients

| Client | Type | Flux autorisé | Redirection / usage |
|---|---|---|---|
| `synapse` | confidentiel | authorization code | callback `https://oryma.local/_synapse/client/oidc/callback` ; secret `OIDC_SYNAPSE_SECRET` |
| `console` | public | authorization code + PKCE S256 | `https://oryma.local/admin/*` ; aucun secret navigateur |
| `admin-api` | confidentiel | client credentials seulement | appels sortants de l’API vers Keycloak ; aucun flux navigateur |

Paramètres injectés dans le conteneur `admin-api` :

| Variable | Valeur / rôle |
|---|---|
| `KEYCLOAK_ISSUER` | issuer public : `https://${ORYMA_HOST}/auth/realms/oryma` ; valeur stricte du claim `iss` |
| `KEYCLOAK_JWKS_INTERNAL_URL` | JWKS sur le réseau Compose : `http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs` |
| `KEYCLOAK_ADMIN_CLIENT_ID` | `admin-api` |
| `KEYCLOAK_ADMIN_CLIENT_SECRET` | secret local `ADMIN_API_OIDC_SECRET`, jamais committé |

Le client `console` est public : Authorization Code avec PKCE S256 seulement ; les flux implicite, password/direct grant et client credentials sont désactivés. Un access token obtenu par ce client porte naturellement `azp: "console"` ; le mapper ajoute `admin-api` à `aud`.

## Jeton de la console reçu par l’API

L’API accepte seulement un **access token** issu du client `console` qui satisfait toutes les conditions suivantes :

| Vérification | Valeur attendue |
|---|---|
| `iss` | `https://oryma.local/auth/realms/oryma` |
| `aud` | contient `admin-api` |
| `exp`, `nbf` | jeton en cours de validité |
| rôle | `realm_access.roles` contient `agent` ou `admin` |
| route réservée | `realm_access.roles` contient `admin` |

Le mapper d’audience du client `console` ajoute explicitement `admin-api` au claim `aud`. Ne pas accepter le rôle depuis le corps HTTP, un en-tête personnalisé ou `resource_access`.

## TOTP et enrôlement

`CONFIGURE_TOTP` est une action requise par défaut dans le royaume. L’enrôlement conserve cette action jusqu’à sa réussite et impose le changement du mot de passe temporaire. L’API ne crée jamais un compte actif sans ces deux actions requises.

## Refus et audit

Un refus `403` dû à un rôle insuffisant inscrit l’action `TENTATIVE_ACCES_REFUSE` dans `audit_log`. `details` est limité à `{"route":"/api/v1/agents","motif":"ROLE_INSUFFISANT"}` : aucune adresse IP, aucun jeton, en-tête `Authorization`, identifiant de session ou contenu de message n’est admis.
