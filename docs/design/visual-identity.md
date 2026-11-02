# Oryma — Système d’identité visuelle

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>product/product-requirements.md</code></p>

## 1. Positionnement visuel

Oryma doit inspirer **confiance et simplicité** : aussi simple qu’une messagerie grand public, avec la sobriété d’un outil institutionnel. `Oryma` est le nom d’affichage et `msgsov` reste l’identifiant technique historique à migrer progressivement dans la configuration.

### Principes directeurs

| Principe | Application |
|---|---|
| Aussi simple qu’une messagerie grand public | On garde l’interface d’Element ; on personnalise la marque, les couleurs et les textes |
| La sécurité se voit sans se subir | Indicateur de chiffrement, appareil vérifié, niveau de classification en toutes lettres |
| Peu de choix, des messages clairs | Un seul chemin de connexion, des erreurs expliquées en français simple |
| Pensé pour une connexion irrégulière | Interface légère, aucune ressource externe, états « hors ligne » explicites |
| Souveraineté jusque dans l’interface | Aucune police, image ni script chargés depuis un service tiers |

### Ce que Oryma ne doit pas devenir

- Une interface refaite à zéro au lieu d’un thème d’Element.
- Un écran chargé de jargon cryptographique.
- Un outil où la couleur seule porte une information.

## 2. Deux interfaces

1. **Client des agents** : Element Web, configuré (`config.json`) et habillé (thème, logo, page d’accueil, textes de connexion).
2. **Console d’administration** : page web légère servie par le service FastAPI, authentifiée par Keycloak. Les écrans A1 à A4 exigent le rôle `admin` ; l’écran A5 est ouvert à tout agent actif.

## 3. Couleurs

### 3.1 Palette de marque (mode clair)

| Élément | Valeur proposée |
|---|---|
| Couleur principale | Bleu nuit `#1F3A5F` |
| Accent décoratif | Or `#C9A227` (bordures et séparateurs seulement : trop clair pour du texte) |
| Succès | Vert `#2E7D32` |
| Danger / révocation | Rouge `#C62828` |
| Fond | `#F6F8FB` |
| Texte | `#1B2430` |

Les contrastes sont à vérifier avec un outil dédié avant la démonstration. Un thème sombre est facultatif.

### 3.2 Niveaux de classification

Badge avec **texte et icône**, jamais la couleur seule : « Diffusion restreinte » en bleu, « Confidentiel » en rouge sombre. Dans Element, le niveau figure dans le nom de la salle ; le badge n’existe que dans la console.

### 3.3 Variables CSS de départ

```css
:root {
  --color-primary: #1F3A5F;
  --color-accent: #C9A227;   /* décoratif uniquement */
  --color-success: #2E7D32;
  --color-danger: #C62828;
  --color-bg: #F6F8FB;
  --color-text: #1B2430;
  --font-sans: system-ui, "Segoe UI", Roboto, sans-serif;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
}
```

## 4. Typographie

Pile système (`system-ui`, `Segoe UI`, `Roboto`, `sans-serif`), **jamais de police distante**. Taille de base 16 px, interligne 1,5.

## 5. Grille, densité et responsive

- Zones tactiles d’au moins 44 px.
- La console défile horizontalement dans ses tableaux sans faire défiler la page.
- Mise en page souple : relative units, flexbox ou grille.
- Tests sur téléphone Android et ordinateur ([compatibilité](../testing/README.md)).

## 6. Composants de référence (console)

### 6.1 Boutons

Primaire (bleu nuit), secondaire (contour), danger (rouge, réservé à la révocation).

### 6.2 Tableaux et listes

Liste des agents avec nom, ministère, fonction, rôle, statut ; filtres ; défilement horizontal sur petit écran.

### 6.3 Badges et statuts

`actif` (vert + libellé), `revoque` (rouge + libellé), niveaux de classification (icône + texte).

### 6.4 Dialogue de révocation

Deux gestes : bouton, puis confirmation avec rappel (« L’agent perdra l’accès sur tous ses appareils immédiatement. ») et saisie du nom. Le résultat s’affiche **étape par étape** ; une étape en échec apparaît en rouge avec un bouton « Réessayer ».

### 6.5 États système

Hors ligne, chargement, erreur, succès : toujours un texte explicite.

## 7. Écrans du client des agents

| Réf. | Écran | Contenu et comportement |
|---|---|---|
| S1 | Accueil / connexion | Logo, phrase d’accueil, bouton unique « Se connecter avec mon compte professionnel » ; redirection vers Keycloak |
| S2 | Connexion Keycloak | Identifiant, mot de passe, puis code TOTP ; erreurs claires |
| S3 | Première connexion | Configuration guidée du TOTP : QR code, saisie du premier code |
| S4 | Liste des conversations | Salles, messages privés, indicateur « chiffré » ; niveau dans le nom de la salle |
| S5 | Conversation | Messages, envoi de fichiers ; le nom rappelle le niveau |
| S6 | Création de salle classifiée | **Dans la console (A5), pas dans Element** |
| S7 | Vérification de l’appareil | Sécuriser la sauvegarde des clés et vérifier ses appareils, sans jargon |
| S8 | Annuaire | Coupé du prototype |
| S9 | Accès révoqué | « Votre accès a été retiré. Contactez votre administrateur. » |

## 8. Écrans de la console d’administration

| Réf. | Écran | Contenu et comportement |
|---|---|---|
| A0 | Tableau de bord administrateur | Accueil après connexion admin, raccourcis vers les opérations et derniers événements d’audit |
| A1 | Liste des agents | Tableau, filtres, boutons « Enrôler » et « Révoquer » |
| A2 | Enrôlement | Formulaire : nom complet, ministère, fonction, rôle ; mot de passe temporaire affiché une seule fois |
| A3 | Confirmation de révocation | Confirmation, saisie du nom, résultat étape par étape |
| A4 | Journal d’audit | Liste chronologique en lecture seule |
| A5 | Création de salle classifiée | Nom, membres (agents actifs), niveau, résumé des règles ; liste « Mes salles » |

## 9. États et messages

| Situation | Message ou comportement |
|---|---|
| Hors ligne | « Connexion perdue : les messages seront envoyés au retour du réseau » |
| Compte non enrôlé | « Ce compte n’est pas autorisé sur cette messagerie. » |
| Code TOTP erroné | « Code incorrect. Vérifiez l’heure de votre téléphone et réessayez. » |
| Message expiré | Le message est purgé du serveur à l’échéance ; une copie déjà reçue sur un appareil peut rester visible (limite documentée) |
| Échec partiel de révocation | Étape en échec en rouge, bouton « Réessayer » |

## 10. Parcours applicatifs

### 10.1 Plan de navigation

```text
Agent :
  S1 Accueil ──> S2 Keycloak ──(1re fois)──> S3 Config TOTP ──┐
                     │                                        v
                     └──────(déjà configuré)──────────> S7 Vérification appareil
                                                              v
                  S4 Conversations <──> S5 Conversation
                         └── (création de salle classifiée : console A5)
  Session fermée par un admin ───────────────────────────> S9 Accès révoqué

Administrateur :
  Connexion (SSO + TOTP) ──> A0 Tableau de bord ──> A1 Liste des agents ──> A2 Enrôlement
                                  ├──> A3 Révocation
                                  ├──> A4 Journal d’audit
                                  └──> A5 Salle classifiée
```

### 10.2 F1 — Première connexion d’un agent enrôlé

1. L’administrateur enrôle l’agent (A2) ; l’agent reçoit ses identifiants par un canal convenu.
2. L’agent ouvre l’adresse (S1) et se connecte.
3. Keycloak impose un nouveau mot de passe.
4. Configuration du TOTP (S3).
5. Retour sur Element, invitation à sécuriser la sauvegarde des clés (S7).
6. Arrivée sur la liste des conversations (S4).

### 10.3 F2 — Connexion courante

Identifiant et mot de passe (S2), code TOTP, arrivée sur S4. En cas d’erreur : message explicite, essais limités par Keycloak.

### 10.4 F3 — Envoyer un message chiffré

Element chiffre sur l’appareil, Synapse stocke et transmet du chiffré, l’appareil du destinataire déchiffre. Dans une salle classifiée, le message sera purgé du serveur à l’échéance.

### 10.5 F4 — Envoyer un fichier

Element chiffre le fichier localement avant le téléversement ; Synapse stocke un fichier illisible.

### 10.6 F5 — Créer une salle classifiée

Dans la console (A5) : nom, membres, niveau ; le service crée la salle ([ADR-008](../adr/008-classified-rooms-service-account.md)) ; les membres acceptent l’invitation dans Element.

### 10.7 F6 — Enrôler un agent

A1 → A2 → compte Keycloak (TOTP obligatoire), enregistrement, audit ; l’agent apparaît « actif ».

### 10.8 F7 — Révoquer un agent pendant une conversation

A1 → A3 : confirmation, séquence en six étapes affichée. Côté agent révoqué : session fermée, S9, connexion refusée. Côté groupe : renouvellement de la clé de session (à vérifier).

### 10.9 F8 — Intrus

Un compte non enrôlé tente de se connecter : refus à Keycloak. Une invitation vers un compte non agent actif est refusée par le service.

### 10.10 F9 — Épreuve « Le serveur ne lit rien »

Phrase repère, export de la base, capture du trafic : aucun clair.

## 11. Langues

Français par défaut. Moré (`mos`) ou dioula (`dyu`) en bonus : traduction des 40 à 60 chaînes les plus visibles ; le reste utilise la langue de repli du client (comportement exact à vérifier dans Element). Les traductions sont relues par un locuteur natif avant la démonstration.

## 12. Accessibilité

Contrastes suffisants, navigation au clavier, libellés explicites, aucune information portée par la seule couleur, textes lisibles sans zoom sur téléphone.

## 13. Écriture produit

- Phrases courtes, en français simple.
- Dire ce qui s’est passé, pourquoi, et quoi faire.
- Aucun jargon cryptographique dans les messages à l’agent.
- Ne jamais promettre plus que le système ne garantit (par exemple : ne pas dire qu’un message « disparaît » de tous les appareils).
