# Journal des changements

Les changements notables de msgsov sont consignés dans ce fichier. Le projet suit les principes de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et adoptera le versionnage sémantique à partir de sa première version publiée.

## [Non publié]

### Ajouté

- Cadrage initial et suite documentaire : cahier des charges, termes de référence, PRD, SRS, contrat système et invariants, architecture, spécification de l’API d’administration, dictionnaire de données, identité visuelle et parcours.
- Guide de développement à deux, stratégie de tests, scénario de démonstration et guide de déploiement (certificat pour téléphone Android inclus).
- ADRs 001 à 010 : Matrix, Synapse et Element, Keycloak, PostgreSQL, Caddy, FastAPI, Docker Compose, salles classifiées, client web installable, licence AGPL-3.0.
- Modèles GitHub pour les issues et pull requests, politique de sécurité et règles de contribution.

### Sécurité

- Interdiction explicite des secrets, des clés privées et des données réelles dans le dépôt.
- Exigences initiales : chiffrement de bout en bout, enrôlement préalable avec second facteur, révocation immédiate, audit en ajout seul.
