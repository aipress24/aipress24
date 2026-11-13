# Changements, semaine 40 2026 (25 septembre – 2 octobre)

La semaine compte 28 commits hors fusions sur 125 fichiers, plus trois migrations. Elle a porté quatre chantiers : le cycle de la commande, repris sur arbitrage ; les écrans de ventes et la licence Creative Commons ; un Business Wall créé en double ; et les actions de l'espace de travail qui modifiaient des données sur un simple lien.

## Newsroom : la commande appartient à celui qui la passe ([#0362](https://trello.com/c/kORNrh5a/362))

**Le propriétaire d'une commande est le rédacteur en chef qui la passe.** Le journaliste qui l'écrira en devient le destinataire, dans une colonne à part. Jusqu'ici, la commande née d'un sujet appartenait au journaliste, et la commande créée directement ne nommait personne : c'est pourquoi elle n'arrivait chez aucun destinataire (#0357). Une migration a basculé les commandes existantes nées d'un sujet.

**Le destinataire lit la commande, il ne la modifie pas.** Seul son propriétaire la modifie, la valide, l'annule ou la supprime. Les autres rédacteurs en chef du média pour lequel elle est passée la lisent aussi. La même règle sert à la liste, à l'ouverture par lien et au compteur de la Newsroom.

**« Valider » et « Annuler » rejoignent le menu.** Une commande validée s'affiche « Validée », une commande annulée « Annulée ». Dans les deux cas, le destinataire est prévenu par la cloche et par un courriel qu'il ne peut pas désactiver, puisque la commande l'engage. Valider exige un destinataire.

**Accepter un sujet ouvre le formulaire de la commande, prérempli.** Le rédacteur en chef y saisit la date de parution avant de créer la commande. Côté sujet, la date qui portait ce nom s'appelle désormais « Cette proposition prend fin le ».

**Le bouton « Nouveau », retiré la semaine dernière, revient.** Une commande peut être passée sans sujet ; le formulaire demande alors le journaliste destinataire.

**« Commande passée par » désigne le média du sujet**, fixé dès l'acceptation, et non plus l'organisation de la première personne qui enregistrait la commande. Le même enregistrement refuse désormais d'attribuer une commande ou un avis d'enquête à une organisation que l'utilisateur ne représente plus : un Business Wall resté sélectionné après le retrait d'un rôle le permettait.

**La page d'une commande porte la barre de navigation des articles**, en haut et en bas.

**Le sujet ne se « publie » plus, il s'envoie.** Les actions deviennent « Envoyer » et « Retirer », le statut « Envoyé ». Le module Sujets est réservé aux membres des Business Walls de la presse : média, journaliste, agence de presse.

**Une seule définition du rédacteur en chef** sert aux sujets, aux commandes et à l'écran des ventes. L'écran des ventes en avait une seconde, fondée sur le seul titre KYC. Ce titre ne compte plus que pour le média de la personne. Le compteur de la tuile Sujets, qui comptait des sujets reçus que la liste ne montrait pas, applique la même règle.

## Ventes et achats

**Le titre d'un article vendu ouvre enfin l'article** ([#0365](https://trello.com/c/XnU5ZOuV/365)). Le lien pointait vers une adresse qui n'existe pas, sur les pages Ventes et Achats, et dans le courriel d'une consultation offerte.

**Les ventes affichent la part de l'éditeur** ([#0364](https://trello.com/c/AacXVchb/364)), la moitié du montant selon les CGV, par vente et en cumul. Elle est calculée en centimes, arrondie au centime le plus proche.

**Les types de vente portent leur libellé partout.** Une consultation offerte s'affichait « consultation_gift ». Ventes, Achats, Mes achats et l'export comptable lisent désormais la même table de libellés.

**Le bandeau « Gérer les modalités » ne s'adresse plus qu'aux gestionnaires du Business Wall** ([#0366](https://trello.com/c/T7Y83WAR/366)). Un journaliste du média le voyait et tombait sur « Accès non autorisé ».

## Licence Creative Commons ([#0367](https://trello.com/c/zMmvbasO/367))

**Un article sous licence Creative Commons se lit sans payer.** Le choix fait dans le formulaire n'allait pas plus loin que l'article : il est maintenant recopié à la publication. Tout membre lit l'article en entier ; la consultation payante et la cession ne sont plus proposées, et leurs adresses refusent l'achat. Le justificatif de publication reste en vente.

**La consultation offerte d'un article CC est gratuite** : elle passe sans Stripe et prévient les destinataires.

**La mention enregistrée est un code, et non plus son libellé.** Renommer le libellé aurait sinon rendu payants, sans bruit, tous les articles CC. La licence s'affiche « Creative Commons (CC BY-ND) ». Deux migrations ont renommé l'ancienne mention, qui associait deux clauses incompatibles, puis converti les valeurs en codes.

## Business Wall : un mur en double ([#0370](https://trello.com/c/iIj1tEXD/370))

**Une organisation qui a déjà un Business Wall actif ne peut plus en créer un second**, à aucune étape du parcours, y compris pour un administrateur du site. C'est par cette porte qu'un second mur avait remplacé celui de l'Agence TCA, laissant le premier sans organisation.

**Un administrateur qui n'est pas gestionnaire du mur se voit « membre » et non « manager »**, et un bandeau rouge lui rappelle, sur le tableau de bord du mur, qu'il y agit en administrateur.

**Un utilisateur sans organisation qui veut activer un Business Wall est d'abord renvoyé vers ses invitations** (Préférences, Invitation), avant qu'on lui demande de renseigner son organisation.

## Actions de l'espace de travail : POST seulement

**Les actions qui modifient des données ne répondent plus à un simple lien.** Supprimer, publier, dépublier, envoyer, retirer, accepter, refuser, valider, annuler : dix-huit routes n'acceptent plus que des requêtes POST, et le menu les présente comme des boutons de formulaire. Un lien posé sur un autre site pouvait les déclencher au nom d'un utilisateur connecté, son cookie de session accompagnant la navigation.

**Le cookie « se souvenir de moi » n'accompagne plus une requête venue d'un autre site**, comme le cookie de session. Sans ce réglage, il suffisait à authentifier une requête POST venue d'ailleurs.

## Administration

Le tableau de bord compte les communiqués, les événements et les sujets créés, par jour et par semaine.

## Code

Dix enchaînements de tests sur le type sont réécrits en `match`. Le rendu en lecture des formulaires y gagne une méthode à part, et le décodage des choix d'une liste multiple perd une boucle écrite deux fois.

## Tests

Quarante-trois fichiers touchés, dont huit nouveaux, et neuf fichiers Playwright. Le cycle de la commande a ses tests de bout en bout : qui lit, qui modifie, qui valide, ce qu'on refuse au destinataire, ce qu'on lui envoie. Un fichier vérifie que chacune des dix-huit routes refuse un GET, et que le fichier de réglages garde les deux cookies hors des requêtes venues d'ailleurs. La définition du rédacteur en chef, l'attribution de l'organisation et le calcul de la part éditeur ont les leurs. Plusieurs ont été vérifiés dans les deux sens : ils échouent sans leur correctif.

Les tests Playwright publient et dépublient désormais par une requête POST qui porte la session, et vérifient qu'elle n'a pas été renvoyée vers la page de connexion.

## À savoir

- Trois migrations, à appliquer dans l'ordre : `74a6a9b5afe2` (licence recopiée sur l'article publié), `5d004245b5f2` (destinataire des commandes, statut « annulé »), `d04237bc4c0c` (licence en code). La deuxième échange propriétaire et destinataire sur les commandes nées d'un sujet ; son retour arrière ne restitue pas l'organisation « passée par » d'origine.
- `etc/settings.toml` gagne `REMEMBER_COOKIE_SAMESITE = "Lax"`.
- Les commandes directes créées avant cette semaine n'ont pas de destinataire : leur propriétaire doit en nommer un avant de les valider.
- Les données de production de l'Agence TCA restent à nettoyer : le premier Business Wall, sans organisation, est toujours actif.
- Plusieurs points attendent une décision, rassemblés pour la réunion du 2 octobre : la consultation offerte à 0 €, qui enregistre des achats à 0 € visibles dans les ventes ; la mention exacte de la licence CC ; le champ « Format » des articles (#0373), sans lequel le tarif ne dépend pas de l'article ; l'accès des agences de presse à l'achat de droits de reproduction.
