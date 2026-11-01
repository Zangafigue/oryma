# Documentation msgsov

Ce dossier transforme le cadrage de [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) en contrats de produit et d’ingénierie traçables. Il comprend un [guide de déploiement](deployment/README.md) (installation, certificat interne, téléphone Android) et une [note de sécurité](securite.md) qui sert de source à la pièce du dossier de candidature.

## Documents de travail quotidiens

| Document | Usage |
|---|---|
| [development/README.md](development/README.md) | Routine des deux membres, plan du sprint, handoffs et décisions arrêtées |
| [api/README.md](api/README.md) | Registre producteur-consommateur des contrats HTTP |
| [data/data-dictionary.md](data/data-dictionary.md) | Tables, types, enums, relations et propriété des données |
| [deployment/README.md](deployment/README.md) | Installation, adresse unique, certificat interne et téléphone Android |
| [architecture/README.md](architecture/README.md) | Limites de composants et responsables d’implémentation |
| [testing/README.md](testing/README.md) | Niveaux de tests, quatre tests de sécurité prioritaires, liste mobile |
| [demo/mvp-scenario.md](demo/mvp-scenario.md) | Parcours d’intégration, épreuves du jury et script de la vidéo |
| [securite.md](securite.md) | Source de la note de sécurité du dossier de candidature |

## Parcours recommandé

| Ordre | Document | Question traitée |
|---:|---|---|
| 0 | [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) | Quel est le cadrage initial ? |
| 1 | [product/cahier-des-charges.md](product/cahier-des-charges.md) | Quel est le besoin, le périmètre et les contraintes ? |
| 2 | [product/termes-de-reference.md](product/termes-de-reference.md) | Quelle est la mission, l’organisation et l’évaluation ? |
| 3 | [product/product-requirements.md](product/product-requirements.md) | Que construit-on, pour qui, avec quelles priorités ? |
| 4 | [product/software-requirements.md](product/software-requirements.md) | Quel comportement précis doit être testable ? |
| 5 | [architecture/system-contract.md](architecture/system-contract.md) | Qu’est-ce qui ne doit jamais devenir faux ? |
| 6 | [architecture/requirements-traceability.md](architecture/requirements-traceability.md) | Quel composant possède chaque garantie ? |
| 7 | [architecture/system-architecture.md](architecture/system-architecture.md) | Comment le système est-il organisé ? |
| 8 | [api/specification.md](api/specification.md) | Quels contrats HTTP relient la console et le service ? |
| 9 | [design/visual-identity.md](design/visual-identity.md) | Comment l’interface et les parcours se présentent-ils ? |

Les index [product/](product/README.md), [architecture/](architecture/README.md), [api/](api/README.md) et [design/](design/README.md) permettent aussi une lecture directe par domaine. Les décisions structurantes sont conservées dans [adr/](adr/README.md).

## Règles de maintenance

- Ne changez pas la signification d’un identifiant `FR-*`, `NFR-*`, `INV-*`, `BR-*` ou `ERR-*` déjà utilisé.
- Ajoutez un nouvel identifiant pour une nouvelle exigence ; marquez explicitement les exigences retirées ou remplacées.
- Une modification d’invariant doit être répercutée dans le SRS, le contrat système, la traçabilité et les tests liés.
- Une modification du contrat API met à jour la spécification, le registre et les consommateurs dans la même pull request.
- Une modification du modèle de données met à jour le dictionnaire, la migration et les fixtures concernées.
- Un contrat partagé indique son producteur, ses consommateurs, son statut et sa preuve de vérification.
- Une décision structurante a un ADR. Ne supprimez pas les ADRs historiques.
- Les documents décrivent la réalité ou une décision explicite. Les hypothèses sont nommées et ratifiées avant implémentation.
- Aucune affirmation de sécurité n’est écrite dans le dossier de candidature sans preuve exécutable ou démonstration.

## Statut actuel

Cette documentation décrit la cible du prototype avant initialisation du code. Les commandes, mesures de performance et détails d’installation devront être mis à jour avec des preuves au fur et à mesure de l’implémentation. Les noms des membres et l’heure limite du dépôt restent à renseigner.
