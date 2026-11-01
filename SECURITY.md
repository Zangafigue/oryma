# Politique de sécurité d’Oryma

Oryma protège des échanges administratifs. La confidentialité de bout en bout, le contrôle des accès et la traçabilité sont des exigences de conception, pas des améliorations facultatives.

## Versions concernées

Oryma n’a pas encore de version publiée. Les correctifs de sécurité sont intégrés à `main` après vérification. Cette section sera remplacée par une matrice de versions supportées avant toute diffusion.

## Signaler une vulnérabilité

Ne créez pas d’issue publique et ne placez aucune preuve contenant un secret dans une pull request.

Utilisez en priorité la fonctionnalité privée **Report a vulnerability** de l’onglet **Security** du dépôt, lorsqu’elle est activée. À défaut, contactez directement un membre de l’équipe par un canal privé convenu.

Incluez uniquement ce qui est nécessaire :

- composant et version ou commit concernés ;
- description de l’impact ;
- étapes minimales de reproduction avec les comptes de démonstration fictifs ;
- conditions nécessaires à l’exploitation ;
- proposition de correction, si disponible.

N’incluez jamais de secret actif, de jeton réutilisable ou de donnée réelle.

## Règles pour les contributeurs

- Aucun secret, mot de passe, jeton, clé privée (dont la clé de l’autorité de certification de Caddy) ni fichier `.env` ne doit être committé.
- **Aucune cryptographie écrite par l’équipe** : le chiffrement vient exclusivement de Matrix (Olm/Megolm).
- Aucun message ni fichier ne doit apparaître en clair côté serveur, dans la base, les journaux ou le trafic.
- Les appels d’administration exigent un jeton valide et le rôle `admin`, vérifiés côté serveur à chaque requête.
- Seul le proxy publie un port ; les autres services restent sur le réseau interne.
- Les erreurs et journaux ne doivent exposer ni secret ni contenu de message, ni adresse IP inutile.
- Les images et dépendances sont figées à une version précise et mises à jour de manière contrôlée.

## Données et tests

Le développement, les tests et les démonstrations utilisent **exclusivement des comptes et des données fictifs**. Tout test d’intrusion visant un système réel est interdit. Les tests de sécurité s’exécutent uniquement contre une installation locale de l’équipe.

## Divulgation coordonnée

L’équipe demande un délai raisonnable pour analyser et corriger avant toute publication. Les correctifs sont testés contre le scénario signalé et les invariants concernés (voir [docs/architecture/system-contract.md](docs/architecture/system-contract.md)).
