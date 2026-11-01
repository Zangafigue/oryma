# ADR-008 — Création des salles classifiées par un compte de service sans droits d’administration

## Statut

Accepté

## Date

2026-11-01

## Contexte

La classification (Diffusion restreinte, Confidentiel) et l’expiration sont l’innovation retenue. Choisir un niveau dans Element demanderait de modifier son code, ce qui n’est pas réaliste en un jour. La rétention doit être posée dès la création de la salle. Cette décision doit être validée par un test d’environ 30 minutes dès que Synapse démarre.

## Décision

Le service d’administration crée la salle à la demande de l’agent, depuis l’écran A5 de la console, avec un compte de service **sans droits d’administration** : salle privée, événement de chiffrement et politique de rétention du niveau dans l’état initial, agent demandeur au niveau de pouvoir administrateur, membres invités ; le compte de service quitte ensuite la salle. Le niveau figure dans le nom de la salle. **Plan B** : l’agent crée la salle dans Element et un administrateur envoie l’événement de rétention depuis les outils de développement d’Element.

## Alternatives considérées

### Agent crée la salle dans Element, le service pose la rétention après coup

- Avantages : aucun compte de service à créer.
- Inconvénients : il faudrait impersonner l’agent ou lui donner un rôle de gestion.
- Motif du rejet : sert de plan B.

### Rétention globale identique pour toutes les salles

- Avantages : aucun code.
- Inconvénients : un seul niveau possible.
- Motif du rejet : ne permet pas deux niveaux.

### Fork d’Element

- Avantages : niveau choisi dans l’interface.
- Inconvénients : coût et risque élevés.
- Motif du rejet : écartée.

## Conséquences

### Positives

- Aucun code d’Element à modifier ; chiffrement et rétention posés dès la création.
- Compte de service sans droit d’administration ni clé de déchiffrement des messages.
- Le service vérifie que l’agent et tous les membres sont des agents actifs, ce qui empêche d’inviter un compte non enrôlé.

### Contraintes et risques

- Le serveur connaît la durée de rétention de chaque salle, donc son niveau (limite documentée).
- La purge ne supprime que la copie du serveur : un appareil peut garder une copie reçue.
- Le service ne poste aucun message dans la salle : il ne serait pas chiffré.
- Le compte de service est créé avec le secret d’enregistrement de Synapse (mot de passe local désactivé) ; à vérifier à l’installation.

## Références

- FR-040, INV-11, INV-12.
- `docs/architecture/system-architecture.md`, section Création d’une salle classifiée.
