# Cycle Sujet → Commande : synthèse des tickets #0355, #0357 et #0362

_Synthèse SF. Cette version 4 reprend les arbitrages du 2026-09-28 sur la propriété de la commande, les droits de son destinataire, sa validation et son annulation ; la version 3 reprenait la réunion du 2026-09-25. Ce qui reste ouvert tient en §6, ce qui a été écarté en §7._

| Ticket | Titre | État | Lien |
|---|---|---|---|
| #0362 | Cycle de vie de la Commande | Non qualifié | [kORNrh5a](https://trello.com/c/kORNrh5a) |
| #0357 | Commande non parvenue chez son destinataire | En attente retour TCA | [BbdnqOon](https://trello.com/c/BbdnqOon) |
| #0355 | Obligation de publier une proposition pour qu'elle soit envoyée | En attente retour TCA | [dEauKQsz](https://trello.com/c/dEauKQsz) |

## 1. Décision

**Le sujet reste adressé au média, visible des seuls rédacteurs en chef.** C'est la décision de juin, maintenue : « si c'est compliqué d'installer un ciblage, le sujet ne doit alors apparaître que chez les rédacteurs en chef » (décision d'Erick en juin, cité au §7). Le ciblage nominatif est écarté.

**La commande directe existe ; l'application ne filtre pas qui la passe.** Tout journaliste peut en créer une sans passer par un sujet, conformément à la spécification du cycle de publication, dont la matrice de permissions accorde « Créer Commande » au rôle journaliste et précise que « les permissions sont gérées au niveau des rôles (pas individuellement) ». Celui qui en passe une sans y être habilité commet une faute professionnelle ; l'application n'a pas à l'en empêcher.

**La commande appartient à celui qui la passe.** Son propriétaire (`owner_id`) est le rédacteur en chef, ou assimilé, qui la passe au sein d'un média. Le journaliste qui l'écrira en est le **destinataire** (`destinataire_id`) : il la voit, il ne la modifie pas (arbitrage du 2026-09-28). Les deux objets vont donc en sens inverse : le sujet s'adresse à un média, la commande à un journaliste nommé. Pour une commande née d'un sujet, ce journaliste est l'auteur du sujet.

**Le rédacteur en chef valide et annule la commande.** « Valider » la fait passer au statut « Validée » et notifie son destinataire par mail et par la cloche ; « Annuler » la met au statut « Annulée » et le notifie de même. Seul le propriétaire modifie, valide, annule et supprime la commande. Qu'un journaliste puisse refuser ou annuler une commande reçue reste hors sujet.

**Le vocabulaire du sujet change.** « Publier » devient « **Envoyer** » et « Dépublier » devient « **Retirer** », un sujet étant envoyé à une rédaction et non publié. Le statut suit : envoyé, il s'affiche « **Envoyé** ».

**Le périmètre est la presse.** La com' n'est pas traitée, donc la séparation Sujets J / Sujets C envisagée dans #0357 tombe.

## 2. Fonctionnement actuel de l'application

**Le sujet.** Il se crée en brouillon. Son menu dépend du statut et de qui regarde : l'auteur voit Voir, Modifier, Supprimer, puis Envoyer en brouillon ou Retirer une fois envoyé ; le média destinataire voit Voir, Modifier, Accepter et Refuser. Le destinataire est une organisation : le modèle porte un `media_id` et rien d'autre.

**Qui voit un sujet reçu.** Son auteur, et les rédacteurs en chef du média. La qualification de rédacteur en chef tient à l'une de ces deux conditions :

- la personne appartient au média et son profil KYC est `PM_DIR`, `PM_DIR_INST` ou `PM_DIR_SYND` (directeur de la rédaction, institutionnel, syndicat) ;
- ou la personne détient un rôle `BW_OWNER` ou `BWMi`, invitation acceptée, sur le Business Wall actif du média.

La seconde condition couvre en partie la réserve d'Erick selon laquelle « certains journalistes ont parfois un rôle de rédacteur en chef sans en avoir le titre » : gérer le Business Wall du média suffit, le titre n'est pas exigé. Un média sans Business Wall actif ne compte en revanche que sur les trois codes KYC.

**Qui entre dans la Newsroom.** Les journalistes, et eux seuls (rôle `PRESS_MEDIA`). Les gestionnaires RP d'un Business Wall en ont été exclus par un correctif ultérieur, mais le commentaire en tête du module dit encore le contraire et devrait être corrigé.

**Le passage à la commande.** Accepter crée une commande en brouillon et met le sujet en « accepté » ; refuser le met en « refusé ». Dans les deux cas l'auteur est notifié par mail et par la cloche. Le rédacteur en chef qui accepte devient le propriétaire de la commande, l'auteur du sujet son destinataire, et le média du sujet celui qui la passe (« Commande passée par »). La commande reprend du sujet le titre, le texte, le chapô, les dates et les métadonnées (genre, rubrique, sujet, secteur, lieu).

**La commande.** Son propriétaire voit Voir, Modifier, Valider (en brouillon), Annuler (en brouillon ou validée) et Supprimer ; son destinataire et les autres rédacteurs en chef du média ne voient que Voir, et les routes leur refusent le reste. Une commande se crée aussi directement, par le bouton « + New » : le formulaire demande le journaliste destinataire, choisi parmi les membres journalistes. Valider exige un destinataire. Les statuts s'affichent « Validée » (`ACCEPTED`) et « Annulée » (`CANCELLED`), libellés propres à la table des commandes.

## 3. Ce qu'il reste à faire

1. ~~Refuser un `publisher_id` non autorisé sur la commande et sur l'avis d'enquête~~ : fait (§5).
2. ~~Faire nommer le journaliste destinataire au formulaire de commande~~ : fait, dans une colonne `destinataire_id` et non dans `owner_id` (§4).
3. ~~Ouvrir la lecture aux autres rédacteurs en chef du média qui passe la commande~~ : fait (§4).
4. ~~Rétablir le bouton « + New »~~ : fait.
5. ~~Ajouter « Valider » et « Annuler »~~ : fait, avec le statut `CANCELLED` et la notification du destinataire à la validation comme à l'annulation.
6. ~~Renommer « Publier » en « Envoyer » et « Dépublier » en « Retirer », et afficher « Envoyé »~~ : fait. Les routes gardent leurs noms (`publish`, `unpublish`) ; seul l'affichage change, et la table des sujets porte seule le libellé « Envoyé ».

## 4. Qui porte quoi sur une commande : le cas #0357

| | Née d'un sujet accepté | Créée directement |
|---|---|---|
| `owner_id` = `commanditaire_id` | le rédacteur en chef qui accepte | le créateur |
| `destinataire_id` | l'auteur du sujet | le journaliste choisi au formulaire |
| `media_id` | le média du sujet, celui du rédacteur en chef | le média choisi au formulaire, par défaut celui du créateur |
| `publisher_id` (« Commande passée par ») | le média du sujet | l'organisation pour laquelle agit le créateur (§5) |

La commande est visible de son propriétaire, de son destinataire et des rédacteurs en chef du média pour lequel elle est passée (`media_id`). La même expression (`Commande.is_visible_to`) sert à la liste, à la lecture par identifiant et au compteur de la Newsroom ; la qualité de rédacteur en chef est celle du §2 (`app.modules.wip.redac_chef`).

**Ce qui causait #0357.** Jusqu'au 2026-09-28, `owner_id` portait le journaliste sur la commande née d'un sujet (#0225), et le formulaire de commande directe ne proposait que des organisations, rangées dans `media_id`. Aucune colonne ne portait donc le destinataire d'une commande directe : il n'y avait personne à qui la montrer. `media_id` portait en outre deux sens selon la naissance, ce qui a causé #0353.

**Le correctif retenu diffère de celui de la version 3.** Celle-ci proposait d'inscrire le destinataire dans `owner_id`. L'arbitrage du 2026-09-28 retient l'inverse : le propriétaire est celui qui passe la commande, et le destinataire a sa propre colonne. La migration `5d004245b5f2` a basculé les commandes existantes nées d'un sujet : l'ancien `owner_id` devient `destinataire_id`, le rédacteur en chef devient propriétaire, et `publisher_id` prend la valeur de `media_id`.

**Les autres rédacteurs en chef du média lisent ses commandes, sans les modifier.** La modification, la validation, l'annulation et la suppression restent réservées au propriétaire.

## 5. Deux bugs relevés en chemin

**Le destinataire d'un sujet peut le réécrire.** « Modifier » ne dépend que du statut. Un sujet soumis est en `PUBLIC`, qui n'interdit pas la modification. Le média destinataire peut donc réécrire le sujet reçu, puis l'accepter. Le droit de modifier voyage avec le droit de voir, les deux tenant à une règle unique écrite pour fermer un contournement par URL. Il est accepté que le destinataire puisse modifier le Sujet, par exemple pour recadrer ou préciser la forme attendue. Il est de la responsabilité du destinataire du Sujet de ne pas dénaturer complètement le Sujet.

**Une commande pouvait être attribuée à une organisation qu'on ne représente plus.** Corrigé le 2026-09-28. La version 3 décrivait mal le défaut : « Commande passée par » (`publisher_id`) n'est pas un champ du formulaire, personne ne la choisit. Elle est attribuée au premier enregistrement : l'organisation du Business Wall que l'utilisateur gère, sinon la sienne. `can_user_publish_for` vérifiait la valeur présente *avant* cette attribution, donc rien sur un nouveau document, et son résultat n'était que journalisé. Or le retrait d'un rôle ou d'une délégation (`revoke_user_role`, `revoke_partnership`) ne désélectionne pas le Business Wall : un ancien gestionnaire pouvait signer une commande ou un avis d'enquête au nom d'une organisation qu'il ne représente plus.

Le correctif, `assign_publisher`, vérifie l'organisation qu'il attribue et refuse l'enregistrement si l'utilisateur n'y a pas droit ; une organisation déjà attribuée est conservée. Il sert à la commande et à l'avis d'enquête. Sujet, communiqué et événement gardent leur avertissement à l'enregistrement, leur étape d'envoi ou de publication refusant déjà une organisation non autorisée.

Ce point ne relève pas de l'habilitation du §1, qui porte sur l'ancienneté de quelqu'un dans sa propre rédaction. Il s'agit ici de mettre le nom d'une autre organisation sur un document, ce qu'aucune responsabilité professionnelle ne couvre.

À signaler aussi, sans gravité tant que rien ne bouge de ce côté : la condition qui affiche « Accepter » et « Refuser » compare seulement l'organisation, sans appeler la fonction de qualification, que seule la route vérifie. Le menu est donc plus permissif que l'action, et une modification de la règle dans la fonction ne se répercuterait pas sur le menu.

## 6. Ce qui reste ouvert

1. ~~Le destinataire d'une commande peut-il la modifier ?~~ Non (arbitrage du 2026-09-28).
2. **« Une fois la Commande exécutée »** (ticket) n'a pas d'état correspondant : aucun lien ne relie une commande à l'article qui l'exécute. Le propriétaire peut supprimer la commande à tout moment.

## 7. Ce qui a été écarté

Consigné pour que ces points ne se rouvrent pas d'eux-mêmes.

**Le ciblage nominatif du sujet**, c'est-à-dire la désignation d'une personne au sein d'une rédaction comme destinataire. La fonction qui restreint aujourd'hui la visibilité aux rédacteurs en chef est née le 4 juin, sur une demande d'Erick que le commit cite : « tous les membres d'une rédaction reçoivent la même proposition de façon indifférenciée [...] si c'est compliqué d'installer un ciblage, le sujet ne doit alors apparaître que chez les rédacteurs en chef. » Le repli est maintenu. Une revue de sécurité lui a par ailleurs donné le lendemain une seconde fonction, celle de garder l'accès par identifiant à toutes les routes du sujet, qu'une URL directe contournait : la retirer rouvrirait cette faille.

**Le renvoi d'un sujet refusé** vers un autre média. Un sujet écarté laisse son auteur en créer un nouveau, ce qui évite de conserver l'historique des statuts média par média. Jérôme le recommandait ; la raison retenue est de ne pas complexifier davantage l'application.

**La séparation Sujets J / Sujets C**, et l'atterrissage des sujets de communication dans une liste distincte de la Newsroom, le périmètre étant la presse.

**Toute vérification d'habilitation à passer une commande.** La responsabilité est professionnelle.

**Une seule définition du rédacteur en chef** (`app.modules.wip.redac_chef`) sert aux sujets, aux commandes et à l'écran des ventes, qui en avait une seconde fondée sur le seul profil KYC.
