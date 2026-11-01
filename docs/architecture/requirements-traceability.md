# msgsov — Transition des exigences vers l’architecture

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>architecture/system-contract.md</code></p>

## Méthode

Chaque invariant possède exactement un composant responsable. Le propriétaire définit et teste le mécanisme d’application, même lorsque d’autres composants lui transmettent du contexte. Un changement de propriétaire exige la mise à jour simultanée de ce document, de l’architecture et des tests concernés.

## Composants

**Deployment** — Définit les réseaux, volumes, secrets, contrôles d’état et l’installation en une commande.

**EdgeProxy** — Seul point d’entrée : TLS interne, en-têtes de sécurité, journaux d’accès minimaux.

**MessageServer** — Synapse : transporte et stocke des événements chiffrés, applique la rétention, porte les réglages de minimisation des métadonnées.

**IdentityProvider** — Keycloak : authentifie, impose le TOTP, porte les rôles et les comptes de démonstration fictifs.

**AgentClient** — Element Web : seul endroit où le chiffrement est effectué, et où les appareils sont vérifiés.

**AdminService** — FastAPI : enrôle, révoque, crée les salles classifiées ; valide jeton et rôle.

**AuditLedger** — Journal d’audit en ajout seul.

**Store** — PostgreSQL : trois bases isolées.

## Attribution des invariants

### MessageServer

Possède **INV-01** et **INV-09**. Le chiffrement par défaut sur tous les types de salle et l’absence de clair côté serveur sont garantis par la configuration et prouvés par un export de base. La présence, les aperçus d’URL et la conservation des adresses IP sont réglés dans `homeserver.yaml`.

### AgentClient

Possède **INV-02**. Le chiffrement est fourni par les bibliothèques d’Element ; l’équipe n’écrit aucune primitive.

### IdentityProvider

Possède **INV-03**, **INV-04** et **INV-13**. Seuls les comptes créés par enrôlement existent ; l’action requise « Configure OTP » est imposée ; le royaume préconfiguré ne contient que des comptes fictifs.

### AdminService

Possède **INV-05**, **INV-06**, **INV-11** et **INV-12**. Une dépendance commune valide jeton et rôle ; la séquence de révocation ferme Keycloak puis nettoie Synapse ; le service de salles pose le chiffrement et la rétention à la création et ne poste aucun message.

### AuditLedger

Possède **INV-10**. Le compte de base de données du journal est limité aux insertions et aux lectures.

### Deployment

Possède **INV-07** et **INV-08**. Seul le proxy publie un port ; les secrets sont générés au premier lancement et ignorés par Git.

## Table de couverture

| Invariant | Propriétaire unique | Point d’application principal |
|---|---|---|
| INV-01 Chiffrement de bout en bout systématique | MessageServer | Chiffrement par défaut des salles, test d’export de base |
| INV-02 Aucune cryptographie écrite par l’équipe | AgentClient | Revue du dépôt : aucune primitive écrite |
| INV-03 Identité vérifiée | IdentityProvider | Inscription fermée, SSO seul, royaume préconfiguré |
| INV-04 Second facteur obligatoire | IdentityProvider | Action requise TOTP |
| INV-05 Autorisation côté serveur | AdminService | Dépendance commune jeton + rôle |
| INV-06 Révocation immédiate et complète | AdminService | Séquence en quatre étapes rejouables |
| INV-07 Isolation et souveraineté | Deployment | Réseaux Docker, fédération coupée, test de ports fermés |
| INV-08 Secrets et clés hors dépôt | Deployment | `.gitignore`, génération au premier lancement |
| INV-09 Minimisation des métadonnées | MessageServer | Réglages Synapse, journaux d’accès coupés |
| INV-10 Audit en ajout seul | AuditLedger | Droits du compte de base |
| INV-11 Rétention appliquée par niveau | AdminService | État initial de la salle à la création |
| INV-12 Aucun message posté par un service | AdminService | Absence d’envoi de message dans le code et les tests |
| INV-13 Données fictives uniquement | IdentityProvider | Royaume `realm-export.json` |

## Décisions de couplage et cohésion

- **AdminService ne lit jamais de message** : il orchestre Keycloak et Synapse par leurs API et ne touche pas aux tables de Synapse.
- **IdentityProvider reste distinct d’AdminService** : l’authentification forte n’est pas écrite par l’équipe.
- **Le compte de service des salles est distinct du compte d’administration** : un compromis de l’un n’ouvre pas les droits de l’autre.
- **AuditLedger est transversal mais autonome** : les services émettent des événements ; ils ne modifient pas l’historique.
- **Deployment ne contient aucune règle métier** : il fixe l’isolation et les secrets.
- **La console ne contient aucune règle de sécurité** : elle appelle l’API qui vérifie jeton et rôle.
