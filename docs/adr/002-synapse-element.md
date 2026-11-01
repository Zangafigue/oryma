# ADR-002 — Synapse et Element Web configuré, sans fork profond

## Statut

Accepté

## Date

2026-11-01

## Contexte

Il faut un serveur Matrix complet et un client web qui intègre le chiffrement, la vérification des appareils et la sauvegarde des clés, sans écrire de code de sécurité supplémentaire.

## Décision

Utiliser **Synapse** comme serveur et **Element Web** comme client, personnalisés par configuration, thème, logo et textes uniquement. Aucun fork profond ni client écrit sur mesure.

## Alternatives considérées

### Serveurs Matrix plus récents (par exemple Dendrite)

- Avantages : implémentations plus légères.
- Inconvénients : moins complets ou plus jeunes.
- Motif du rejet : Synapse est l’implémentation de référence, la mieux documentée.

### Client écrit avec matrix-js-sdk

- Avantages : contrôle total de l’interface.
- Inconvénients : beaucoup de code de sécurité à écrire, tester et expliquer au jury.
- Motif du rejet : risque disproportionné pour le délai.

### Fork d’Element

- Avantages : personnalisation poussée.
- Inconvénients : coûteux à maintenir et à expliquer.
- Motif du rejet : une configuration et un thème suffisent.

## Conséquences

### Positives

- Chiffrement et vérification des appareils déjà intégrés et éprouvés.
- Interface connue, déjà utilisable sur petits écrans.
- Moins de code à expliquer devant le jury.

### Contraintes et risques

- Le niveau de classification ne peut pas être choisi dans Element sans le modifier : voir [ADR-008](008-classified-rooms-service-account.md).
- Certaines options de configuration dépendent de la version : à vérifier à l’installation.

## Références

- FR-020, FR-050.
- `docs/design/visual-identity.md`.
