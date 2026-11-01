# msgsov — Note de sécurité

<p class="small"><strong>Version :</strong> v1.1, 2026-11-01 · <strong>Dépendance :</strong> <code>architecture/system-contract.md</code></p>

Ce document est la source de la note de sécurité du dossier de candidature (2 pages maximum). La version courte reprend le périmètre, les menaces, les protections, les métadonnées visibles et les limites. **N’y affirmer que ce qui aura été réellement construit et vérifié.**

## 1. Périmètre

Messagerie chiffrée de bout en bout pour agents enrôlés, hébergée sur une infrastructure maîtrisée, sans service tiers. Protocole : Matrix (Olm/Megolm). **Aucune cryptographie n’est écrite par l’équipe.**

## 2. Menaces prises en compte

| Menace | Protection | Invariant |
|---|---|---|
| Serveur curieux ou compromis lisant des messages | Chiffrement de bout en bout sur l’appareil ; le serveur ne stocke que du chiffré | INV-01 |
| Intrus non enrôlé | Inscription publique, accès invité et mot de passe local coupés ; SSO Keycloak seul | INV-03 |
| Mot de passe volé | TOTP obligatoire, anti-force brute | INV-04 |
| Agent parti ou téléphone perdu | Révocation immédiate : Keycloak d’abord, puis appareils et compte Synapse | INV-06 |
| Appel d’administration forgé | Validation du jeton et du rôle à chaque appel | INV-05 |
| Service interne exposé | Un seul port publié (proxy) ; réseau interne | INV-07 |
| Fuite de secret | Secrets hors dépôt, générés au premier lancement, détection avant envoi | INV-08 |
| Altération de l’historique d’administration | Audit en ajout seul | INV-10 |

## 3. Protections mises en place

- **Chiffrement** : activé par défaut pour toutes les salles ; clés sur les appareils.
- **Identité** : comptes créés uniquement par enrôlement ; rôles `admin` et `agent` ; anti-force brute et sessions courtes.
- **Réseau** : TLS interne via Caddy, en-têtes de sécurité ; fédération désactivée ; console d’administration de Keycloak non routée.
- **Conteneurs** : images figées, `no-new-privileges`, `cap_drop: ALL` quand c’est possible, redémarrage automatique.
- **Privilèges** : deux comptes de service Synapse distincts ; le compte qui crée les salles n’a pas de droits d’administration.
- **Audit** : enrôlement, révocation, changement de rôle et création de salle tracés ; ni adresse IP ni contenu.
- **Rétention** : salles classifiées purgées côté serveur à l’échéance de leur niveau.

## 4. Ce que le serveur voit malgré le chiffrement

| Information visible | Mesure de réduction |
|---|---|
| Qui est membre de quelle salle | Inévitable pour acheminer les messages ; accès à la base réservé à l’hébergeur |
| Qui envoie un événement, et quand | Inévitable ; journaux d’accès du proxy désactivés |
| Taille des messages et des fichiers | Non masquée dans le prototype |
| Appareils associés à un compte | Nécessaire au chiffrement ; supprimés à la révocation |
| Adresses IP de connexion | Conservation courte |
| Noms et sujets des salles | Non chiffrés par défaut dans Matrix : ne rien y mettre de sensible |
| Durée de rétention de chaque salle, donc son niveau | Inévitable : le serveur doit la connaître pour la faire respecter ; le nom de la salle porte aussi le niveau |

Le chiffrement protège le contenu, pas l’existence ni le niveau d’une salle.

## 5. Limites connues

- Un **agent révoqué garde ce qu’il a déjà reçu** et déchiffré sur son appareil ; seuls les nouveaux messages lui sont fermés. L’effacement à distance serait la parade (hors périmètre).
- La **purge à expiration** supprime la copie du serveur ; un appareil qui l’a déjà reçue peut la conserver.
- Un **administrateur Keycloak** pourrait ouvrir une session à la place d’un agent depuis un nouvel appareil. Parades : vérification des appareils (signature croisée) et journal d’audit.
- `transfert_interdit` est indicatif : il n’empêche pas techniquement la copie d’un message.
- Un **appareil compromis** (logiciel malveillant) n’est protégé par aucun protocole.
- **Notifications en arrière-plan** et applications natives non couvertes (service tiers, certificat).
- Chiffrement du disque de l’hôte, sauvegardes, scan des images et audit externe sont **à prévoir** hors prototype.
- La sauvegarde des clés d’Element est chiffrée mais stockée sur le serveur : la phrase de récupération doit être forte.
- Pas de montée en charge, ni de fédération, ni d’archivage légal.

## 6. Preuves

| Garantie | Preuve |
|---|---|
| Serveur aveugle | Export de la base : aucune occurrence de la phrase repère ; capture réseau |
| Révocation | Test à deux appareils ; test d’idempotence |
| Intrus | Test de connexion et d’invitation d’un compte non enrôlé |
| Isolation | Test de ports internes fermés |
| Audit | Test du droit d’insertion seule |

Voir [testing/README.md](testing/README.md).

## 7. Règles éthiques

Données et comptes fictifs uniquement. Aucun test d’intrusion visant un système réel : les tests de sécurité ne s’exécutent que contre l’installation locale de l’équipe.
