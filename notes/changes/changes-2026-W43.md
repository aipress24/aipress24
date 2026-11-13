# Changements, semaine 43 2026 (16 – 23 octobre)

La semaine compte 25 commits hors fusions sur 231 fichiers, plus une migration. Elle n'apporte aucune fonction nouvelle aux membres : c'est une semaine d'infrastructure. La file des tâches de fond change de bibliothèque, l'application passe au pilote PostgreSQL psycopg 3, Stripe change de version d'API, et le code perd le prototype qui l'accompagnait depuis l'origine, soit plus de sept mille lignes.

## File des tâches de fond : dramatiq-postgres

**La file des tâches passe de dramatiq-pg à dramatiq-postgres**, et dramatiq à sa version 2.2. La file reste dans la base de l'application, sans Redis. dramatiq-pg retenait dramatiq avant sa version 2 et tenacity avant sa version 9.

**Le passage ne perd aucune tâche en attente.** La migration renomme l'ancienne file, crée la nouvelle, y recopie les messages qui n'étaient pas terminés, puis supprime l'ancienne. Une tâche programmée pour plus tard garde son heure de déclenchement ; une tâche interrompue par l'arrêt des workers est rejouée. Le schéma de la nouvelle file est écrit en toutes lettres dans la migration, pour qu'une montée de version de la bibliothèque ne le change pas en silence.

**Au démarrage, l'application crée la file si elle manque**, et rien de plus. La conversion de l'ancienne file est l'affaire de la migration seule.

**Le tableau de bord `/admin/dramatiq` montre les workers vivants**, d'après le signal de vie que chacun envoie, à côté des compteurs par file et par état. La liste des derniers messages disparaît : la nouvelle file efface un message dès qu'il est traité.

## PostgreSQL : psycopg 3

**L'application se connecte à PostgreSQL avec psycopg 3**, le pilote qu'utilise déjà la nouvelle file. psycopg2 n'est plus installé. Toute adresse de base en `postgres://`, `postgresql://` ou `postgresql+psycopg2://` est réécrite en `postgresql+psycopg://` au chargement de la configuration, ce qui couvre les variables d'environnement existantes.

**Un identifiant d'objet lu dans l'URL est converti en entier avant la requête.** psycopg 3 transmet une chaîne telle quelle, et PostgreSQL refuse de la comparer à une clé numérique : les pages de l'espace de travail ouvertes par leur identifiant échouaient. Un identifiant qui n'est pas un nombre répond désormais « page introuvable ».

## Stripe

**L'application passe à la version `2026-09-30.endive` de l'API Stripe.** Le paiement par carte seule, qui écarte Link et sa confirmation par SMS (#0214), s'exprime désormais par `allowed_payment_method_types`, sur les trois parcours : achat d'un article, consultation offerte, abonnement à un Business Wall. Le second essai sans restriction de moyen de paiement, quand Stripe refuse la première demande, retire bien cette clé.

## Administration

**Le courriel « Reputations updated » ne part plus toutes les heures.** Il n'annonçait rien d'autre que le passage de la tâche planifiée.

## Code

**Le prototype `src/poc` est supprimé**, avec ses tests et la commande `make run-poc` : 46 fichiers, montés seulement quand l'option `POC_ENABLED` était active. L'option disparaît avec lui.

**Les énumérations partagées entre modules vivent dans `app.enums`** : statut et rôles d'un Business Wall, statut d'invitation, statut d'accréditation, produits et statuts d'achat, correspondance entre communautés et rôles. Les libellés des rôles d'un Business Wall les rejoignent. Les anciens emplacements ne les réexportent plus, et une centaine de fichiers importent depuis la nouvelle adresse.

Deux exceptions au vérificateur de types pyrefly sont remplacées par des variables typées, et l'acteur de mise à jour des réputations écrit dans le journal au lieu de la sortie standard.

Montée de version d'advanced-alchemy (1.12), de Pillow (13) et de python-slugify (9).

## Tests

Quatre-vingt-dix-neuf fichiers de tests touchés, dont un nouveau, hors suppression des neuf fichiers du prototype. Le nouveau fichier vérifie la réécriture des adresses de base pour chaque forme reçue. Les autres suivent le déplacement des énumérations, le nouveau paramètre Stripe et le changement de pilote. La migration de la file a été vérifiée sur une copie du schéma de développement : messages en attente, interrompus et différés repris, messages terminés abandonnés. Le schéma figé a été comparé à celui que produit la bibliothèque : ils sont identiques.

## À savoir

- Une migration : `52b861396d51` (file des tâches dramatiq-postgres, PostgreSQL seulement). L'appliquer avant de redémarrer les workers : une application démarrée sur l'ancienne file ne peut plus y déposer de tâches.
- L'adresse de la base de données peut rester en `postgres://` : la configuration la réécrit. Les commandes manuelles (`make test-postgres`, scripts) utilisent désormais `postgresql+psycopg://`.
- La version de l'API Stripe configurée dans le tableau de bord Stripe, en particulier pour les webhooks, doit passer à `2026-09-30.endive`.
- Les points en attente de la semaine 42 restent ouverts : [#0390](https://trello.com/c/Jgv3udNF/390) (logo et bandeau de Fake-Léonard Industries) et [#0391](https://trello.com/c/QeEYcSLP/391) (courriels, côté fournisseur d'envoi).
