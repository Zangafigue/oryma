# msgsov — Contrat système et invariants

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>product/software-requirements.md</code></p>

## Actions autorisées par acteur

| Acteur | Peut | Ne peut pas |
|---|---|---|
| Agent | Échanger messages et fichiers, créer une salle classifiée avec des agents actifs | Enrôler, révoquer, lire l’audit |
| Administrateur | Enrôler, révoquer, changer un rôle, consulter l’audit | Lire une conversation chiffrée ; modifier l’audit |
| Service d’administration | Appeler Keycloak et Synapse dans son périmètre | Lire un message ; décider d’un enrôlement sans administrateur |
| Compte de service Synapse (salles) | Créer une salle, inviter, puis la quitter | Administrer Synapse ; poster un message ; conserver un rôle dans la salle |
| Serveur (Synapse, base) | Transporter et stocker des événements chiffrés, appliquer la rétention | Déchiffrer un message ou un fichier |

## Garanties du système

### Chiffrement

**INV-01 — Chiffrement de bout en bout systématique**  
Toute salle DOIT être chiffrée dès sa création. Aucun message ni fichier NE DOIT apparaître en clair dans la base, les journaux ou le trafic.

**INV-02 — Aucune cryptographie écrite par l’équipe**  
Le chiffrement vient exclusivement de Matrix (Olm/Megolm) via Element. Aucune primitive, aucun protocole ni aucun chiffrement de champ n’est écrit par l’équipe.

### Identité et accès

**INV-03 — Identité vérifiée**  
Seuls des agents préalablement enrôlés PEUVENT se connecter ou être invités. L’inscription publique, l’accès invité et le mot de passe local sont désactivés.

**INV-04 — Second facteur obligatoire**  
Aucune session d’agent n’est établie sans TOTP.

**INV-05 — Autorisation côté serveur**  
Chaque appel d’administration DOIT valider le jeton (signature, émetteur, audience, expiration) et le rôle requis. Un rôle transmis par le client ne remplace jamais cette vérification.

**INV-06 — Révocation immédiate et complète**  
La révocation DOIT exécuter six étapes dans cet ordre : désactivation de l’utilisateur Keycloak, fermeture des sessions Keycloak, suppression de tous ses appareils Synapse, désactivation du compte Synapse, mise à jour du statut en base, puis audit. Chaque étape est rejouable et son résultat est visible.

### Isolation et secrets

**INV-07 — Isolation et souveraineté**  
Seul le proxy publie un port. La fédération est désactivée. Aucun service tiers n’est nécessaire au fonctionnement.

**INV-08 — Secrets et clés hors dépôt**  
Aucun secret, jeton ni clé privée (dont celle de l’autorité de Caddy) n’est committé. Les secrets sont générés au premier lancement.

### Métadonnées et traçabilité

**INV-09 — Minimisation des métadonnées**  
Présence, aperçus d’URL et journaux d’accès sont désactivés ; la conservation des adresses IP est courte. Ce que le serveur voit malgré tout est documenté dans [securite.md](../securite.md).

**INV-10 — Audit en ajout seul**  
Le journal d’audit n’accepte que des insertions et des lectures. Il ne contient ni adresse IP ni contenu de message.

### Classification

**INV-11 — Rétention appliquée par niveau**  
Une salle classifiée porte, dès sa création, la politique de rétention de son niveau. Le serveur purge à l’échéance ; il ne garantit pas l’effacement sur les appareils.

**INV-12 — Aucun message posté par un service**  
Le service d’administration NE DOIT poster aucun message dans une salle chiffrée : il ne serait pas chiffré.

### Données de test

**INV-13 — Données fictives uniquement**  
Les développements, tests et démonstrations n’utilisent que des comptes et données fictifs.

## Interdictions absolues

- Écrire ou modifier une primitive cryptographique.
- Stocker ou journaliser le contenu d’un message ou d’un fichier en clair.
- Exposer un service interne (PostgreSQL, Keycloak, API d’administration, console Keycloak) hors du réseau interne.
- Committer un secret, une clé privée ou un fichier `.env`.
- Tester une intrusion contre un système réel.
- Réactiver l’inscription publique, l’accès invité ou le mot de passe local.

## Gestion des menaces au contrat

| Menace | Protection | Limite connue |
|---|---|---|
| Serveur curieux ou compromis | Chiffrement de bout en bout (INV-01) | Métadonnées visibles (INV-09) |
| Intrus non enrôlé | Enrôlement préalable et SSO (INV-03) | — |
| Vol de mot de passe | TOTP obligatoire (INV-04) | Hameçonnage du TOTP : WebAuthn non retenu |
| Agent révoqué | Révocation en six étapes (INV-06) | Il garde l’historique déjà reçu sur son appareil |
| Administrateur Keycloak malveillant | Vérification des appareils, audit (INV-10) | Il peut ouvrir une session à la place d’un agent depuis un nouvel appareil |
| Appel d’administration forgé | Validation du jeton et du rôle (INV-05) | — |
| Fuite de secret | `.gitignore`, détection avant envoi (INV-08) | — |
| Appareil d’agent compromis | — | Aucun protocole ne protège contre cela |
