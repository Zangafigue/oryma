# msgsov — Product Requirements Document

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>PROJECT_OVERVIEW.md</code></p>

## 1. Problème

| Problème | Conséquence |
|---|---|
| Échanges de service sur des messageries étrangères | Perte de maîtrise des données et des règles |
| Aucun contrôle des accès quand un agent part ou perd son téléphone | Fuite possible d’informations |
| Pas de distinction entre message courant et message sensible | Informations sensibles conservées indéfiniment |

## 2. Personas

**Agent de l’administration (Awa, chargée d’études dans un ministère).** Utilise son téléphone et parfois un ordinateur partagé. Connexion internet irrégulière. Veut envoyer une instruction à son service sans compliquer sa journée. Besoin : simplicité, fiabilité, confiance.

**Administrateur de la messagerie (Moussa, informaticien du ministère).** Enrôle les nouveaux agents, révoque ceux qui partent. Besoin : agir vite, voir qui a fait quoi, sans pouvoir lire les conversations.

**Responsable de la sécurité (Dr Ouédraogo, direction du numérique).** Veut des garanties vérifiables, pas des promesses. Besoin : preuves (tests, documentation, limites connues).

Les personas sont fictifs.

## 3. Solution proposée

Une messagerie aussi simple que WhatsApp pour un agent, mais dont le serveur appartient à l’État et ne peut rien lire.

## 4. Périmètre et priorités (MoSCoW)

### 4.1 Accès et identité

- **Must** : connexion par SSO avec TOTP obligatoire ; rejet des comptes non enrôlés.
- **Could (coupé)** : WebAuthn.

### 4.2 Messagerie

- **Must** : messages 1-à-1 et groupes chiffrés de bout en bout ; fichiers chiffrés.

### 4.3 Administration

- **Must** : enrôlement et révocation par un administrateur ; journal d’audit.
- **Could (coupé)** : annuaire par ministère et fonction.

### 4.4 Classification

- **Should** : salles Diffusion restreinte et Confidentiel ; expiration automatique selon le niveau.

### 4.5 Interface et déploiement

- **Must** : installation en une commande ; utilisable sur PC et téléphone.
- **Should** : interface en moré ou dioula ; tests pytest des fonctions de sécurité.

## 5. Hors périmètre

Appels audio/vidéo, fédération, applications natives, notifications en arrière-plan, montée en charge, archivage légal, effacement à distance.

## 6. Récits utilisateurs

| Réf. | En tant que… | Je veux… | Afin de… | Critère d’acceptation |
|---|---|---|---|---|
| US-01 | Agent | me connecter avec mon compte et un code TOTP | prouver mon identité | Connexion refusée sans second facteur |
| US-02 | Agent | échanger avec mon service dans un groupe | travailler en équipe | Messages visibles uniquement par les membres |
| US-03 | Agent | envoyer un fichier | partager un document de service | Fichier illisible dans le stockage du serveur |
| US-04 | Agent | créer une salle « Confidentiel » | limiter la durée de vie de ses messages | Les messages de la salle expirent à la durée du niveau |
| US-05 | Administrateur | enrôler un nouvel agent | lui donner accès | Compte créé, TOTP imposé à la première connexion |
| US-06 | Administrateur | révoquer un agent | couper son accès immédiatement | Plus de connexion ni de nouveaux messages lisibles |
| US-07 | Administrateur | consulter le journal d’audit | savoir qui a fait quoi | Chaque enrôlement et révocation est tracé |
| US-08 | Responsable sécurité | lire ce que le serveur voit | évaluer le risque | Liste documentée des métadonnées |

## 7. Critères de réussite

- Les quatre épreuves de sécurité passent en démonstration sans intervention manuelle.
- Tous les tests pytest réussissent sur une installation propre.
- L’installation complète tient en une commande, sans service tiers.
- Chaque membre répond sans aide à une question du jury sur le code de sécurité.

## 8. Risques

| Risque | Probabilité | Impact | Parade |
|---|---|---|---|
| Configuration OIDC Synapse–Keycloak plus longue que prévu | Élevée | Élevé | Royaume préconfiguré en fichier, test précoce |
| Délai trop court | Élevée | Élevé | Priorités Must, innovation limitée à une fonctionnalité, ordre de sacrifice |
| Création de salle par le service plus longue que prévu | Moyenne | Moyen | Test de 30 minutes en premier, plan B de l’ADR-008 |
| Un membre ne sait pas expliquer le code | Moyenne | Éliminatoire | Relecture croisée, chacun explique un composant à l’autre |
| Message en clair côté serveur (erreur de configuration) | Faible | Éliminatoire | Chiffrement par défaut sur toutes les salles, test automatisé |
| Panne pendant la démonstration | Moyenne | Moyen | Redémarrage automatique, vidéo de secours, jeu de données reproductible |
