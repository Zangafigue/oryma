# ADR-001 — Matrix comme protocole de messagerie chiffrée

## Statut

Accepté

## Date

2026-11-01

## Contexte

Le sujet impose un chiffrement de bout en bout reposant sur un protocole éprouvé et open source (Signal, Matrix, MLS ou XMPP/OMEMO) et interdit toute cryptographie écrite par l’équipe. Le prototype doit être livré en environ un jour : le protocole doit donc fournir serveur, client, groupes, fichiers et multi-appareils déjà prêts.

## Décision

Utiliser **Matrix** (chiffrement Olm pour les échanges entre appareils, Megolm pour les salles de groupe) au niveau d’engagement « Étendre et adapter ». La fédération est désactivée.

## Alternatives considérées

### XMPP avec OMEMO

- Avantages : serveur (par exemple Prosody) et client Conversations disponibles.
- Inconvénients : chiffrement de groupe et de fichiers moins uniforme selon les clients ; client plus difficile à adapter.
- Motif du rejet : possible mais plus fragile pour un prototype en un jour.

### Signal (libsignal)

- Avantages : bibliothèque de chiffrement éprouvée.
- Inconvénients : serveur lourd à héberger, client et groupes à construire autour de la bibliothèque.
- Motif du rejet : trop long pour le délai.

### MLS (OpenMLS)

- Avantages : protocole moderne.
- Inconvénients : bibliothèque seulement, aucun produit complet.
- Motif du rejet : trop long pour le délai.

## Conséquences

### Positives

- Serveur, client, chiffrement de groupe, fichiers et multi-appareils existent déjà ; l’équipe configure et orchestre.
- Le serveur ne stocke que des événements chiffrés, ce qui répond à la règle éliminatoire du message en clair.
- Matrix est utilisé par des administrations (la messagerie Tchap de l’État français en est un exemple à sourcer avant de le citer).

### Contraintes et risques

- Les métadonnées (qui, quand, quelle salle, taille) restent visibles du serveur : voir [system-contract.md](../architecture/system-contract.md).
- Le comportement de renouvellement des clés après un départ doit être vérifié par un test à deux appareils.
- Les noms d’options et versions doivent être vérifiés dans la documentation de la version retenue.

## Références

- INV-01, INV-02, INV-07.
- `docs/securite.md`.
