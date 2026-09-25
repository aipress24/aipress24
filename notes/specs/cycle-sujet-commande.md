# Cycle Sujet → Commande : synthèse des tickets #0355, #0357 et #0362

_Synthèse SF. Cette version 3 reprend la réunion du 2026-09-25 et l'arbitrage qui a suivi. Ce qui reste ouvert tient en §6, ce qui a été écarté en §7._

| Ticket | Titre | État | Lien |
|---|---|---|---|
| #0362 | Cycle de vie de la Commande | Non qualifié | [kORNrh5a](https://trello.com/c/kORNrh5a) |
| #0357 | Commande non parvenue chez son destinataire | En attente retour TCA | [BbdnqOon](https://trello.com/c/BbdnqOon) |
| #0355 | Obligation de publier une proposition pour qu'elle soit envoyée | En attente retour TCA | [dEauKQsz](https://trello.com/c/dEauKQsz) |

## 1. Décision

**Le sujet reste adressé au média, visible des seuls rédacteurs en chef.** C'est la décision de juin, maintenue : « si c'est compliqué d'installer un ciblage, le sujet ne doit alors apparaître que chez les rédacteurs en chef » (décision d'Erick en juin, cité au §7). Le ciblage nominatif est écarté.

**La commande directe existe ; l'application ne filtre pas qui la passe.** Tout journaliste peut en créer une sans passer par un sujet, conformément à la spécification du cycle de publication, dont la matrice de permissions accorde « Créer Commande » au rôle journaliste et précise que « les permissions sont gérées au niveau des rôles (pas individuellement) ». Celui qui en passe une sans y être habilité commet une faute professionnelle ; l'application n'a pas à l'en empêcher.

**Il manque « Valider » et « Annuler » au menu de la commande**, faute de quoi elle n'aboutit pas. Le détail du parcours n'est pas à traiter : qu'un journaliste puisse refuser ou annuler une commande reçue reste hors sujet.

**Le vocabulaire du sujet change.** « Publier » devient « **Envoyer** » et « Dépublier » devient « **Retirer** », un sujet étant envoyé à une rédaction et non publié. Le statut suit : envoyé, il s'affiche « **Envoyé** ».

**Un statut « annulé » est ajouté**, pour la commande que son commanditaire annule.

**Le périmètre est la presse.** La com' n'est pas traitée, donc la séparation Sujets J / Sujets C envisagée dans #0357 tombe.

## 2. Fonctionnement actuel de l'application

**Le sujet.** Il se crée en brouillon. Son menu dépend du statut et de qui regarde : l'auteur voit Voir, Modifier, Supprimer, puis Publier en brouillon ou Dépublier une fois publié ; le média destinataire voit Voir, Modifier, Accepter et Refuser. Le destinataire est une organisation : le modèle porte un `media_id` et rien d'autre.

**Qui voit un sujet reçu.** Son auteur, et les rédacteurs en chef du média. La qualification de rédacteur en chef tient à l'une de ces deux conditions :

- le profil KYC est `PM_DIR`, `PM_DIR_INST` ou `PM_DIR_SYND` (directeur de la rédaction, institutionnel, syndicat) ;
- ou la personne détient un rôle `BW_OWNER` ou `BWMi`, invitation acceptée, sur le Business Wall actif du média.

La seconde condition couvre en partie la réserve d'Erick selon laquelle « certains journalistes ont parfois un rôle de rédacteur en chef sans en avoir le titre » : gérer le Business Wall du média suffit, le titre n'est pas exigé. Un média sans Business Wall actif ne compte en revanche que sur les trois codes KYC.

**Qui entre dans la Newsroom.** Les journalistes, et eux seuls (rôle `PRESS_MEDIA`). Les gestionnaires RP d'un Business Wall en ont été exclus par un correctif ultérieur, mais le commentaire en tête du module dit encore le contraire et devrait être corrigé.

**Le passage à la commande.** Accepter crée une commande en brouillon et met le sujet en « accepté » ; refuser le met en « refusé ». Dans les deux cas l'auteur est notifié par mail et par la cloche. La commande reprend du sujet le titre, le texte, le chapô, les dates et les métadonnées (genre, rubrique, sujet, secteur, lieu).

**La commande.** Son menu propose Voir, Modifier et Supprimer, ni « Valider » ni « Annuler ». Le bouton « + New » est masqué depuis le 21 septembre, mais `/wip/commandes/new/` reste ouverte et crée toujours une commande.

## 3. Ce qu'il reste à faire

1. **Refuser un `publisher_id` non autorisé** sur la commande et sur l'avis d'enquête (§5). Indépendant du reste, et prioritaire.
2. **Faire nommer le journaliste destinataire au formulaire de commande**, et l'inscrire dans `owner_id` (§4). C'est le correctif de #0357 ; il n'ajoute ni colonne ni branche de visibilité.
3. **Ouvrir la lecture aux rédacteurs en chef du média du commanditaire**, en liste comme par identifiant, avec les deux précautions du §4.
4. **Rétablir le bouton « + New »** de la page Commandes, un changement d'une ligne, après le point 2 : une commande directe que son destinataire ne voit pas ne sert à rien.
5. **Ajouter « Valider » et « Annuler »** au menu de la commande, avec le statut « annulé » qui manque à l'énuméré et la notification de l'auteur à la validation.
6. **Renommer « Publier » en « Envoyer » et « Dépublier » en « Retirer »**, et afficher « Envoyé » là où le sujet affiche « Publié ». Renommer les actions ne coûte rien ; le libellé du statut est plus délicat. Envoyer met le sujet en `PUBLIC`. Cet énuméré est partagé avec les articles, les communiqués, les événements et les avis d'enquête, où « Publié » est juste. Il faut donc un libellé propre au sujet, que la table des sujets peut porter seule en redéfinissant le rendu de sa colonne de statut.

## 4. Pourquoi une commande directe n'arrive pas : le cas #0357

Une commande n'est visible que de deux personnes, celle inscrite dans `owner_id` et celle inscrite dans `commanditaire_id`. Ce que ces colonnes portent dépend de la naissance de la commande ; tout se joue là.

| | Née d'un sujet accepté | Créée directement |
|---|---|---|
| `owner_id` | le journaliste auteur du sujet, qui écrira : **le destinataire** | le créateur |
| `commanditaire_id` | le rédacteur en chef qui accepte | le créateur |
| `media_id` | le média de ce rédacteur en chef : **le média du commanditaire** | l'organisation choisie au formulaire |

**Sur la commande née d'un sujet, nous sommes d'accord.** `media_id` est bien le média du commanditaire ; le code le dit dans son propre commentaire : « `media_id` mirrors the sujet's, so the new commande lives in the rédac chef's own newsroom ». Le destinataire occupe `owner_id`, que la règle de visibilité couvre déjà : il voit la commande, sans qu'il y ait rien à ajouter.

**Sur la commande créée directement, non.** Le formulaire n'offre que des organisations, et celle qu'on choisit tombe dans `media_id`, la colonne qui signifie « média du commanditaire » dans l'autre cas. La même colonne porte donc deux sens opposés, ce qui est la cause de #0353 : l'affichage du destinataire et celui du média commanditaire ont dû apprendre à distinguer les deux naissances pour ne plus mentir. La conséquence est plus lourde encore : aucune colonne ne porte le destinataire d'une commande directe. D'où #0357 : il n'y a personne à qui la montrer.

**Le correctif tient donc à une colonne qui dise vrai, non à une branche de visibilité.** Le plus simple est de faire nommer un journaliste au formulaire et de l'inscrire dans `owner_id`, comme lors de l'acceptation d'un sujet. Trois gains s'ensuivent :

- la règle de visibilité actuelle suffit, sans branche ni colonne nouvelle : le destinataire voit la commande comme `owner`, le commanditaire comme `commanditaire` ;
- `media_id` retrouve un sens unique, celui du média du commanditaire, ce qui permet à l'affichage de cesser de distinguer les deux naissances ;
- la commande dit enfin à qui elle s'adresse, ce qu'Erick demandait dans #0357 : « le rédacteur en chef peut passer une commande à un journaliste ».

**Reste la question des rédacteurs en chef.** Qu'ils voient les commandes de leur propre rédaction demande une branche sur `media_id`, indépendante de ce qui précède, et qui aura alors un sens unique. Deux précautions s'imposent pour l'écrire.

La liste et la lecture par identifiant doivent changer **ensemble**. Le dépôt porte déjà la leçon, dans un commentaire laissé par le correctif de #0225 : « la liste le dit ; la lecture par clé primaire doit être d'accord. » Une branche ajoutée d'un seul côté donne une commande qu'on voit dans sa liste sans pouvoir l'ouvrir, ou l'inverse.

**Ouvrir la lecture ouvre aussi la modification**, faute d'y veiller. `Commande` ne définit pas de `can_edit` ; la classe de base autorise alors la modification à quiconque passe le contrôle d'accès. Le rédacteur en chef qui verra la commande pourra donc la réécrire, ce qui est exactement le défaut relevé sur le sujet au §5. À trancher en écrivant la branche, pas après.

## 5. Deux bugs relevés en chemin

**Le destinataire d'un sujet peut le réécrire.** « Modifier » ne dépend que du statut. Un sujet soumis est en `PUBLIC`, qui n'interdit pas la modification. Le média destinataire peut donc réécrire le sujet reçu, puis l'accepter. Le droit de modifier voyage avec le droit de voir, les deux tenant à une règle unique écrite pour fermer un contournement par URL. Il est accepté que le destinataire puisse modifier le Sujet, par exemple pour recadrer ou préciser la forme attendue. Il est de la responsabilité du destinataire du Sujet de ne pas dénaturer complètement le Sujet.

**Une commande peut être attribuée à une organisation qu'on ne représente pas.** La fonction `can_user_publish_for` est appelée à l'enregistrement pour vérifier l'organisation portée par « Commande passée par ». Elle répond, son résultat n'est que journalisé, et l'enregistrement se poursuit. Un journaliste peut donc signer une commande du nom de n'importe quelle organisation. Le code le sait, puisqu'il pose la question avant de passer outre.

Le défaut est systématique. Cinq écrans appellent cette fonction à l'enregistrement et se bornent à un avertissement dans les journaux ; trois d'entre eux (sujet, communiqué, événement) rattrapent la vérification à l'étape « Publier », qui refuse et le dit à l'utilisateur. La commande et l'**avis d'enquête** n'ont pas d'étape équivalente : pour eux l'avertissement est le dernier mot. L'API publique, elle, rejette un `publisher_id` non autorisé ; c'est le comportement à reprendre dans les deux écrans qui manquent.

Ce point ne relève pas de l'habilitation du §1, qui porte sur l'ancienneté de quelqu'un dans sa propre rédaction. Il s'agit ici de mettre le nom d'une autre organisation sur un document, ce qu'aucune responsabilité professionnelle ne couvre.

À signaler aussi, sans gravité tant que rien ne bouge de ce côté : la condition qui affiche « Accepter » et « Refuser » compare seulement l'organisation, sans appeler la fonction de qualification, que seule la route vérifie. Le menu est donc plus permissif que l'action, et une modification de la règle dans la fonction ne se répercuterait pas sur le menu.

## 6. Ce qui reste ouvert

1. Le destinataire d'une commande peut-il la modifier ? A priori non.

## 7. Ce qui a été écarté

Consigné pour que ces points ne se rouvrent pas d'eux-mêmes.

**Le ciblage nominatif du sujet**, c'est-à-dire la désignation d'une personne au sein d'une rédaction comme destinataire. La fonction qui restreint aujourd'hui la visibilité aux rédacteurs en chef est née le 4 juin, sur une demande d'Erick que le commit cite : « tous les membres d'une rédaction reçoivent la même proposition de façon indifférenciée [...] si c'est compliqué d'installer un ciblage, le sujet ne doit alors apparaître que chez les rédacteurs en chef. » Le repli est maintenu. Une revue de sécurité lui a par ailleurs donné le lendemain une seconde fonction, celle de garder l'accès par identifiant à toutes les routes du sujet, qu'une URL directe contournait : la retirer rouvrirait cette faille.

**Le renvoi d'un sujet refusé** vers un autre média. Un sujet écarté laisse son auteur en créer un nouveau, ce qui évite de conserver l'historique des statuts média par média. Jérôme le recommandait ; la raison retenue est de ne pas complexifier davantage l'application.

**La séparation Sujets J / Sujets C**, et l'atterrissage des sujets de communication dans une liste distincte de la Newsroom, le périmètre étant la presse.

**Toute vérification d'habilitation à passer une commande.** La responsabilité est professionnelle.

**Une remise en ordre reste souhaitable**, sans rapport avec les décisions : le dépôt porte deux définitions concurrentes du rédacteur en chef, celle décrite au §2 et une seconde dans l'écran des ventes, qui ne regarde que le profil KYC, sans le Business Wall ni l'organisation.
