# msgsov — Termes de référence

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>product/cahier-des-charges.md</code></p>

## 1. Objet de la mission

Concevoir, réaliser et documenter un prototype fonctionnel de messagerie instantanée souveraine destinée aux agents de l’administration publique du Burkina Faso, dans le cadre du sprint technique pré-hackathon 2026.

## 2. Justification

L’usage de messageries grand public pour des échanges de service expose l’administration à des risques de confidentialité et de dépendance. Une solution open source, hébergée par l’État et chiffrée de bout en bout répond à cet enjeu de souveraineté numérique.

## 3. Objectifs de la mission

- **Général** : doter l’administration d’une messagerie sécurisée et maîtrisée.
- **Spécifiques** :
  1. Livrer un socle de sécurité conforme (chiffrement de bout en bout, hébergement souverain, identité vérifiée, révocation, métadonnées minimisées).
  2. Livrer une fonctionnalité innovante démontrée.
  3. Documenter la solution (README, note de pré-projet, note de sécurité).

## 4. Résultats attendus

| Résultat | Indicateur |
|---|---|
| Prototype installable en une commande | `docker compose up` démarre tous les services |
| Socle de sécurité fonctionnel | Les quatre épreuves de sécurité passent en direct |
| Innovation démontrée | Démonstration de classification et d’expiration |
| Compatibilité PC et téléphone | Un échange entre un PC et un téléphone Android est démontré |
| Dossier complet | Cinq pièces déposées avant le 1er novembre 2026 |

## 5. Méthodologie

1. **Réutiliser** des briques open source éprouvées (Synapse, Element, Keycloak, Caddy, PostgreSQL).
2. **Écrire uniquement ce qui manque** : le service d’administration et la configuration.
3. **Prouver** chaque exigence de sécurité par un test automatisé ou une démonstration.
4. **Documenter honnêtement** les limites.

## 6. Organisation de l’équipe

| Rôle | Responsabilités |
|---|---|
| Membre A — infrastructure et identité | Docker Compose, Caddy, PostgreSQL, Synapse, Keycloak, SSO et TOTP, durcissement, rétention, note de sécurité |
| Membre B — service d’administration et produit | FastAPI, console d’administration, création de salles classifiées, thème et traduction d’Element, tests, README et note de pré-projet |

Chaque membre doit pouvoir expliquer l’ensemble du socle de sécurité. La répartition des tâches ne dispense pas de comprendre le reste.

## 7. Calendrier de l’organisateur

| Étape | Date |
|---|---|
| Dépôt des dossiers | jusqu’au 1er novembre 2026 |
| Tri sur dossier | 2 au 3 novembre 2026 |
| Entretiens techniques | 4 au 5 novembre 2026 |
| Annonce des finalistes | 6 novembre 2026 |
| Finale de 72 heures | 7 au 9 novembre 2026 |

## 8. Évaluation

Dossier sur 65 points (innovation 25, qualité technique et ergonomie 15, open source et documentation 15, note de sécurité 10), entretien sur 35 points (épreuves en direct). Bonus plafonnés à 10 points : contribution amont (+5), langue nationale (+3), tests automatisés (+2).

## 9. Règles éliminatoires

- Cryptographie développée par l’équipe.
- Message en clair côté serveur.
- Test d’intrusion visant un système réel.
- Incapacité d’un membre désigné à expliquer le code ou les mécanismes de sécurité.
