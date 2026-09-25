# Changements, semaine 39 2026 (18 – 25 septembre)

La semaine compte 39 commits hors fusions sur 69 fichiers, plus trois migrations. Elle a porté deux chantiers et un imprévu : le parcours qui mène d'un sujet proposé à une commande passée, les images qui s'effaçaient des pages, et deux montées de version qui ont empêché l'application de démarrer.

## Newsroom : du sujet proposé à la commande

**Un sujet accepté ou refusé ne s'annonce plus « archivé ».** Les deux issues écrivaient le même statut : un auteur consultant sa liste ne pouvait pas savoir si sa proposition avait été retenue ou écartée. Une migration ajoute les deux statuts qui manquaient, « accepté » et « refusé », que chaque issue écrit désormais.

**Les métadonnées du sujet suivent dans la commande** : genre, rubrique, sujet, secteur, lieu. Elles étaient perdues à l'acceptation ; le journaliste les ressaisissait sur une commande qui venait pourtant de son propre texte.

**Dépublier ou supprimer un sujet revient à son auteur.** Le rédacteur en chef sollicité ne peut plus le faire : il accepte ou il refuse.

**Un sujet accepté, refusé ou archivé ne s'ouvre plus en modification.** L'écran restait atteignable une fois l'issue prononcée. Il répond maintenant que l'élément ne peut plus être modifié ; les menus ne proposent plus l'action.

**Une commande ne se crée plus directement.** Le bouton « Nouveau » quitte la page des commandes : une commande naît d'un sujet accepté, de rien d'autre.

**Et le média porté par la commande est le bon.** Suite du correctif de la semaine dernière ([#0353](https://trello.com/c/Mc63INFr/353)) : les deux origines d'une commande, sujet accepté ou création par un commanditaire, rangent le média à des places différentes ; l'écran lisait toujours la même sans distinguer les cas.

## Statuts et messages en français

Les statuts s'affichaient dans tous les tableaux de l'espace de travail tels qu'ils sont écrits dans le code : `pending`, `public`, `rejected`. Ils portent maintenant un libellé lisible. Les messages d'erreur des modèles de la newsroom, de la comroom et de l'eventroom sont passés au français au même moment.

## Avis d'enquête

**L'écran de ciblage montre la photo, le nom et l'adresse des experts sollicités**, là où il n'alignait qu'une liste.

**Un expert sans Business Wall peut à nouveau répondre** (#0164). Le correctif posé la semaine dernière partait du constat que la réponse semblait se perdre, et en concluait qu'un Business Wall actif était la condition manquante : l'envoi était bloqué, un bandeau invitait à en créer un. Vérification faite, la réponse est bien enregistrée sans Business Wall. Le verrou et son bandeau sont retirés ; la cause du symptôme d'origine est ailleurs.

## Images et identité visuelle

**Renouveler ou refaire son Business Wall ne fait plus perdre son identité visuelle.** Logo et bandeau étaient attachés au mur qui les avait reçus, et l'organisation n'en gardait rien : un nouveau mur repartait nu ; l'ancien, suspendu, conservait les images. Un nouveau mur les reprend désormais du précédent, et une migration a rempli ceux qui étaient déjà dans ce cas.

**Les encarts « Aipress24 vous informe » ne cassent plus.** Leur image avait été enregistrée sous une adresse signée à durée limitée, périmée depuis : la page affichait une erreur de signature en lieu et place de la photo. Douze encarts ont été réécrits vers l'adresse stable, chacun vérifié.

**Les captures d'écran étaient écrites à une adresse que l'application ne lisait pas.** Le réglage en double a été supprimé : deux noms désignaient le même stockage, les environnements n'en renseignant qu'un, si bien que le travail de capture écrivait d'un côté quand le reste de l'application lisait de l'autre.

**Le stockage de fichiers vérifie le certificat de son serveur en production.** Un seul réglage commande le chiffrement et cette vérification. Il était à « non » : les fichiers voyageaient chiffrés vers un serveur dont l'identité n'était pas contrôlée. Testé contre le serveur de production avant d'être activé.

## Administration

**Un administrateur voit tous les messages du Wall**, et non plus seulement ceux des membres qu'il suit ; la modération depuis la page elle-même en était impraticable.

Le tableau de bord perd des métriques financières désactivées de longue date et gagne un compteur d'articles. Son calcul de statistiques passe en tâche de fond, hors du temps d'affichage de la page.

## Dépendances

Une mise à jour de routine a monté deux paquets qui ne passent pas.

**SQLAlchemy 2.1 rend l'application impossible à démarrer.** La nouvelle version rend privé un élément interne dont dépend `sqlalchemy-utils`, qui n'a pas encore de version compatible: la version est plafonnée en l'attendant.

**Flask-Security 5.9 est plafonné aussi**, le temps de réécrire un patch local qui s'appuie sur deux noms devenus privés.

**Ce patch ne servait à rien depuis le début.** En tentant la montée de version, on a constatéque le patch ne s'appliquait jamais, sans le signaler. L'en-tête de cache qu'il devait corriger partait malformé sur chaque réponse d'authentification depuis qu'il existe. Corrigé, avec le test qui l'aurait montré.

## Tests

Vingt-sept fichiers touchés. Le parcours du sujet porte les siens de bout en bout : qui peut dépublier, ce qui est recopié, ce qui devient non modifiable. Trois autres correctifs portent chacun le leur, celui des images, celui du certificat et celui de l'en-tête de cache, chaque fois vérifié dans les deux sens : le test échoue sans son correctif.

Une vingtaine de tests ont par ailleurs été retirés. Ils vérifiaient que Python refuse un argument manquant, qu'une classe déclarée abstraite l'est, ou qu'un objet de test rend ce que son constructeur a reçu : du travail de relecture déguisé en filet de sécurité.

## À savoir

- Deux versions sont plafonnées dans `pyproject.toml`, avec la raison écrite sur place. Lever la première demande que `sqlalchemy-utils` publie une version compatible ; lever la seconde demande de réécrire le patch d'en-tête de cache, ou mieux de le porter en amont pour ne plus l'avoir à charge.
- Le compteur d'articles du tableau de bord est en cours.
