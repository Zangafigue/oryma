# Scénario d’intégration et de démonstration du prototype

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>testing/README.md</code></p>

## But

Ce scénario est le parcours d’intégration commun avant chaque fusion vers `main`, et le script des épreuves du jury et de la vidéo. Il utilise exclusivement des comptes fictifs.

## Histoire démontrée

Un administrateur enrôle des agents de deux ministères fictifs. Deux agents échangent des messages et un fichier chiffrés, sur PC et sur téléphone. Le serveur est inspecté : il ne contient aucun message en clair. Une salle « Confidentiel » voit ses messages expirer. Un agent est révoqué en pleine conversation de groupe et perd immédiatement l’accès. Un intrus non enrôlé est rejeté.

## Jeu de données synthétique

### Ministères fictifs

`MIN-DEMO-A` et `MIN-DEMO-B`.

### Comptes de démonstration

| Identifiant | Rôle | Ministère | Statut |
|---|---|---|---|
| `admin.demo` | `admin` | `MIN-DEMO-A` | enrôlé |
| `agent.demo1` | `agent` | `MIN-DEMO-A` | enrôlé |
| `agent.demo2` | `agent` | `MIN-DEMO-A` | enrôlé |
| `agent.demo3` | `agent` | `MIN-DEMO-B` | enrôlé |
| `intrus.demo` | — | — | **non enrôlé** |

Aucun mot de passe réel n’est utilisé ; les mots de passe de démonstration sont générés et ne figurent pas dans ce dépôt.

### Messages de test

Une phrase repère, par exemple `TEST-JURY-001`, pour l’épreuve du serveur aveugle.

## Parcours et résultats attendus

### 1. Installation et connexion — A

- `docker compose up` sur une machine propre : tous les services sont `healthy`.
- `agent.demo1` se connecte avec mot de passe puis TOTP.
- **Résultat attendu :** arrivée sur la liste des conversations, sans avertissement de certificat.

### 2. Échange chiffré — A et B

- `agent.demo1` et `agent.demo2` créent un groupe et échangent du texte et un fichier.
- **Résultat attendu :** les messages s’affichent chez les deux ; un indicateur de chiffrement est visible.

### 3. Le serveur ne lit rien — A

- Envoyer `TEST-JURY-001` ; exporter la base `synapse` et chercher la phrase ; inspecter le trafic entre Caddy et Synapse.
- **Résultat attendu :** aucune occurrence en clair ; contenu chiffré seulement.

### 4. Révocation — B (console) et A (vérification)

- `admin.demo` révoque `agent.demo2` pendant une conversation de groupe.
- **Résultat attendu :** la console affiche chaque étape ; l’agent révoqué perd la session, ne peut plus se reconnecter et ne lit plus les nouveaux messages.

### 5. Intrus — A

- `intrus.demo` tente de se connecter, puis un agent tente de l’inviter.
- **Résultat attendu :** refus à la connexion ; invitation impossible.

### 6. Salle classifiée et expiration — B

- `agent.demo1` crée depuis la console une salle « Confidentiel » ; envoie un message ; la durée de démonstration expire.
- **Résultat attendu :** le message est purgé du serveur à l’échéance (variable `DEMO_RETENTION` activée) ; le nom de la salle porte le niveau.

### 7. Compatibilité mobile — A et B

- Un échange entre le PC et le téléphone Android ; une révocation vue sur le téléphone.
- **Résultat attendu :** les messages passent dans les deux sens ; l’écran « Accès révoqué » s’affiche sur le téléphone.

### 8. Audit — B

- `admin.demo` consulte le journal d’audit.
- **Résultat attendu :** enrôlements, révocation et création de salle sont tracés, sans adresse IP ni contenu.

## Handoffs à vérifier

| Du… | Au… | Contenu | Preuve |
|---|---|---|---|
| A | B | Royaume Keycloak avec clients et rôles | Connexion de la console |
| A | B | Comptes de service Synapse et secrets | Création d’une salle de test |
| B | A | `POST /agents` et `POST …/revoke` | Test à deux appareils |
| B | A | `DEMO_RETENTION=true` | 5 min Diffusion restreinte / 2 min Confidentiel |

## Scénarios négatifs obligatoires

- Compte non enrôlé : rejeté.
- Jeton absent ou expiré : `401`.
- Agent sans rôle `admin` appelant `POST /agents` : `403` et ligne d’audit.
- Révocation rejouée : même état, sans effet de bord.
- Étape de révocation en échec : signalée, réessayable.
- Invitation d’un compte non agent actif dans une salle classifiée : refusée.
- Ports internes (PostgreSQL, Keycloak, API) : non joignables depuis l’extérieur.

## Preuves de démonstration

- Vidéo de 3 minutes avec des comptes fictifs.
- Journaux et captures nettoyés (aucun secret, aucune donnée réelle).
- Résultats des tests pytest.

## Script de la vidéo (3 minutes maximum)

| Temps | Séquence |
|---|---|
| 0:00–0:20 | Problème et solution, schéma d’architecture |
| 0:20–1:10 | Échange chiffré entre deux agents (texte et fichier), base sans clair |
| 1:10–1:50 | Révocation en pleine conversation de groupe |
| 1:50–2:35 | Salle « Confidentiel » dont les messages expirent |
| 2:35–3:00 | Open source, licences, limites connues, conclusion |

Répéter le scénario au moins une fois avant l’enregistrement.

## Critère de réussite

Les parcours 1 à 8 se déroulent sans intervention manuelle imprévue, les scénarios négatifs passent, et chaque membre sait expliquer ce qui se passe à chaque étape.
