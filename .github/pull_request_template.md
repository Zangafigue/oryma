## Résumé

Décrivez le problème résolu et le résultat obtenu. Restez centré sur l’intention du changement.

## Issue liée

Closes #

## Type de changement

- [ ] Fonctionnalité
- [ ] Correction
- [ ] Documentation
- [ ] Refactorisation sans changement de comportement
- [ ] Tests ou outillage
- [ ] Sécurité
- [ ] Configuration ou déploiement

## Vérification

Indiquez les commandes exécutées et les résultats observés. Pour l’interface, ajoutez les navigateurs, la taille d’écran (PC et téléphone) et les vérifications clavier utiles.

```text
commande — résultat
```

## Impacts

- **Exigences / invariants concernés :**
- **API / base de données / configuration :**
- **Sécurité / métadonnées visibles du serveur :**
- **Interface / accessibilité / mobile :**
- **Déploiement / retour arrière :**

Écrivez « Aucun » lorsqu’une ligne ne s’applique pas ; ne laissez pas une question importante implicite.

## Coordination

- **Responsable du bloc (A ou B) :**
- **Consommateur ou handoff concerné :**
- **Contrat partagé et statut :**
- **Fichiers sensibles annoncés :**

Pour un contrat partagé, liez le registre API, le dictionnaire de données, le guide de déploiement ou l’ADR concerné et indiquez l’accord de l’autre membre.

## Checklist

- [ ] Le changement est limité à une intention cohérente.
- [ ] Les tests pertinents passent localement.
- [ ] `docker compose up` démarre toujours l’ensemble.
- [ ] Aucun secret, jeton, clé privée, fichier `.env` ou donnée réelle n’est inclus.
- [ ] Aucune cryptographie écrite par l’équipe n’est ajoutée.
- [ ] Aucun message ni fichier n’apparaît en clair côté serveur (base, journaux, trafic).
- [ ] Les rôles sont vérifiés côté serveur si le changement touche l’API d’administration.
- [ ] Les erreurs et échecs partiels sont visibles ; aucun échec silencieux.
- [ ] La documentation, l’API, le changelog et les ADRs concernés sont à jour.
- [ ] Les contrats partagés ont été acceptés par l’autre membre.
- [ ] L’interface est utilisable au clavier et sur téléphone, sans couleur comme seul indicateur.
- [ ] Je relis le diff final et je confirme qu’il ne contient pas de changement sans rapport.
