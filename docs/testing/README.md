# Stratégie de tests msgsov

## Objectif

Prouver chaque garantie de sécurité par un test automatisé ou une démonstration reproductible, et empêcher les régressions sur les épreuves du jury.

## Niveaux de tests

| Niveau | Cible | Outil |
|---|---|---|
| Unitaire | Dépendance jeton + rôle, séquence de révocation (clients simulés), règles de salles | pytest |
| Intégration | Service d’administration contre Keycloak et Synapse locaux | pytest + Docker Compose |
| Sécurité | Intrus, révocation, absence de clair en base, ports internes fermés | pytest |
| Démonstration | Parcours du [scénario](../demo/mvp-scenario.md) | Manuel guidé |
| Compatibilité | PC et téléphone Android | Manuel, liste ci-dessous |

## Répartition minimale par composant

### AdminService

- Jeton absent, invalide, expiré : `401`.
- Rôle insuffisant : `403` avec ligne d’audit.
- Enrôlement : utilisateur Keycloak créé avec TOTP imposé ; ligne d’audit.
- Révocation : six étapes dans l’ordre ; reprise après échec partiel ; idempotence.
- Salles : refus d’un membre non agent actif ; refus d’un niveau inconnu ; aucune salle partielle en cas d’échec.

### MessageServer et chiffrement

- Aucune occurrence de la phrase repère dans un export de la base `synapse`.
- Toute salle créée par le service est chiffrée.

### Deployment

- Seul le port 443 (et 80 pour la redirection) est joignable depuis l’extérieur.
- `docker compose up` démarre depuis zéro.

### AuditLedger

- Le compte du service ne peut ni modifier ni supprimer une ligne.

### Client

- Connexion SSO + TOTP ; message et fichier ; écran « Accès révoqué ».

## Tests de contrat prioritaires

| Contrat | Preuve |
|---|---|
| `POST /agents` | Réponse conforme + mot de passe temporaire affiché une seule fois |
| `POST /agents/{id}/revoke` | Étapes retournées ; `502` avec `ERR-033` en cas d’échec |
| `POST /rooms` | Niveau dans le nom ; durée de vie retournée |
| Erreurs | Format commun avec `request_id` |

## Quatre tests de sécurité à écrire en premier

1. **Intrus** : un compte non enrôlé est rejeté à la connexion et à l’invitation.
2. **Révocation** : un agent révoqué ne peut plus se connecter ni lire les nouveaux messages (à vérifier avec deux appareils).
3. **Serveur aveugle** : un message envoyé n’apparaît jamais en clair dans un export de la base.
4. **Ports fermés** : PostgreSQL, Keycloak et l’API d’administration ne sont pas joignables depuis l’extérieur.

## Données de test

Uniquement les comptes fictifs du [scénario](../demo/mvp-scenario.md). Aucun secret réel dans les fixtures. Les mots de passe de test sont générés localement.

## Base de données et migrations

Les migrations SQL numérotées s’appliquent sur une base vide et sur une base existante. Vérifier le droit d’insertion seule sur `audit_log`.

## Temps et expiration

L’expiration par rétention dépend d’un intervalle de purge : pour les tests et la démonstration, la variable `DEMO_RETENTION` règle des durées courtes. Les noms exacts des options Synapse sont à vérifier dans la documentation de la version retenue.

## Commandes cibles

À créer avec le squelette applicatif ; elles ne doivent pas être documentées comme fonctionnelles avant d’exister.

```text
make up        # démarrer l’ensemble
make test      # tests pytest
make lint      # Ruff
make secrets   # générer les secrets locaux
make down      # arrêter sans détruire les volumes
```

## Garde de pull request

- Les tests pertinents passent.
- `docker compose up` démarre toujours.
- Aucun secret détecté.
- Aucune cryptographie ajoutée.

## Gestion d’un test instable

Un test instable est noté, isolé et corrigé avant la fusion suivante ; il n’est pas ignoré en silence.

## Compatibilité mobile (manuel)

- [ ] Connexion avec mot de passe et TOTP sur téléphone.
- [ ] Message et fichier envoyés du PC vers le téléphone, et inversement.
- [ ] Salle de groupe avec au moins un appareil mobile et un PC.
- [ ] Révocation d’un agent connecté sur téléphone : écran « Accès révoqué » et plus aucun nouveau message.
- [ ] Rotation de l’écran et clavier sans masquer la zone de saisie.
- [ ] Comportement sur réseau lent (simulation dans les outils du navigateur).
- [ ] Console d’administration lisible sur téléphone.

## Checklist d’un nouveau comportement

- [ ] Exigence ou invariant identifié.
- [ ] Test écrit ou scénario de démonstration mis à jour.
- [ ] Erreurs et reprises testées.
- [ ] Aucun contenu de message ni secret dans les journaux.
- [ ] Documentation et registre API à jour.
