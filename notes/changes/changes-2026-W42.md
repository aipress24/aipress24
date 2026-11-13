# Changements, semaine 42 2026 (9 – 16 octobre)

La semaine compte 41 commits hors fusions sur 98 fichiers, plus deux migrations. Elle a porté trois chantiers : la gestion des réponses à un avis d'enquête, où le journaliste peut désormais refuser une proposition ; le parrainage, nouvelle page de l'espace social ; et une série de corrections sur les images, les courriels et Stripe.

## Newsroom : les réponses à un avis d'enquête ([#0384](https://trello.com/c/mI0Mv7KF/384))

**Le journaliste peut refuser la proposition d'un expert.** Une réponse positive n'avait jusqu'ici d'autre issue que le rendez-vous. Le bouton « Refuser la proposition » la classe désormais « Proposition refusée ». L'expert lit, dans son espace Opportunités, que la rédaction a pris connaissance de son retour et a choisi de ne pas donner suite. Le bouton « Rétablir » revient en arrière.

**La contribution de l'expert s'affiche là où le journaliste décide.** La page des réponses et le formulaire de proposition de rendez-vous reprennent la note que l'expert a jointe à sa réponse.

**Les deux listes de profils montrent les vignettes** : « Notifier les participants » ([#0389](https://trello.com/c/fWJ9RqBr/389)) et « Gestion des rendez-vous » ([#0392](https://trello.com/c/7UqNRPkt/392)).

**Les courriels partent après l'enregistrement**, pour la confirmation et l'annulation d'un rendez-vous comme pour l'invitation à acheter le justificatif de publication. Un serveur de courrier lent ou en panne retardait ou annulait jusqu'ici l'enregistrement lui-même, cloche comprise ; un courriel pouvait aussi annoncer une invitation que la base n'avait pas gardée. C'est la cause probable du quart d'heure de retard de la cloche signalé dans [#0378](https://trello.com/c/QhxBK2KO/378).

## Swork : le parrainage

**Une page « Parrainage » permet d'inviter des proches à rejoindre AiPRESS24.** Le membre saisit une ou plusieurs adresses, séparées par des espaces, des virgules ou des points-virgules. Les adresses invalides sont signalées, les doublons écartés. Chaque destinataire reçoit un courriel au nom du membre, envoyé depuis contact@aipress24.com ; la page en montre le texte.

**Un membre envoie au plus cinquante invitations sur sept jours glissants.** Chaque envoi est consigné dans une nouvelle table, qui sert au décompte ; la page indique combien d'invitations restent.

## Images

**Un PNG recadré garde sa transparence** ([#0377](https://trello.com/c/qnCtxiAU/377)). L'outil de recadrage remplissait le fond en noir : le logo d'AiPRESS24, sans fond, ressortait en carré noir. Logos, bandeaux, galerie du Business Wall, images des articles, communiqués et événements sont concernés. Les images déjà recadrées ne sont pas réparées : il faut les déposer à nouveau.

**Les articles, communiqués et événements partagent un seul gabarit d'édition des images.** Il en existait trois copies identiques, que le correctif de transparence avait dû modifier une à une.

**`/media` annonce le type d'un fichier d'après une table fixe**, et non plus d'après la base de types du serveur. Sur un serveur sans `/etc/mime.types`, les images WebP et les tableaux ODS partaient comme données brutes ; la CI sous Rocky Linux l'a révélé. Un fichier `.svg` ou `.html` déposé avant l'introduction de la liste blanche reste servi comme données brutes.

## Business Wall et Stripe

**La page d'un Business Wall abonné ne plante plus** ([#0377](https://trello.com/c/qnCtxiAU/377)). La bibliothèque Stripe ne renvoie plus des dictionnaires, et la lecture du produit souscrit échouait.

**La bibliothèque Stripe passe en version 16, et l'application fixe la version de l'API Stripe** (`2026-08-26.dahlia`) au lieu de suivre celle du compte.

**Le texte d'activation d'un Business Wall gratuit est celui demandé** ([#0388](https://trello.com/c/DffD1YVN/388)) : Stripe demande une carte, aucun prélèvement n'est effectué.

## Ventes

**Le prix d'un article suit son genre, écrit avec sa catégorie** ([#0374](https://trello.com/c/JcufstjK/374)). « GENRES / Enquête » n'était pas reconnu, et le prix retombait sur le premier produit venu. « News » l'est aussi désormais.

## Profil d'un membre

Les onglets « Activités » et « Groupes », sans contenu, ne s'affichent plus. L'onglet Profil gagne des marges.

## Code

Montée de ty (0.0.87) et de ruff, avec les corrections qu'elles demandent, dont `import datetime as dt` partout. La feuille de style de Tom Select, chargée par la plupart des modules, quitte le module KYC pour les fichiers statiques communs.

## Tests

Vingt-deux fichiers de tests touchés, dont deux nouveaux. Le parrainage a les siens : découpage et validation des adresses, quota, contenu du courriel. Les vignettes des deux listes de profils, le refus et le rétablissement d'une proposition, l'envoi des courriels après enregistrement et le gabarit commun des images ont les leurs. Le type servi par `/media` est vérifié pour chaque extension, y compris quand la base de types du serveur l'ignore. Plusieurs ont été vérifiés dans les deux sens : ils échouent sans leur correctif.

Sur la CI Ubuntu, seul uv est installé hors projet : nox, inutilisé, entrait en conflit avec un paquet Debian.

## À savoir

- Deux migrations, à appliquer dans l'ordre : `e7a1b2c3d4f5` (statut « Proposition refusée », PostgreSQL seulement), `af48d7388211` (journal des invitations de parrainage).
- La version de l'API Stripe est maintenant fixée dans le code. Les webhooks configurés dans le tableau de bord Stripe doivent utiliser la même version.
- Le logo du Business Wall d'AiPRESS24 est à déposer à nouveau (#0377).
- Le parrainage n'écarte pas les adresses de personnes déjà inscrites, et le lien du courriel mène à la page d'accueil, non à l'inscription.
- Les courriels qui n'arrivent plus ([#0391](https://trello.com/c/QeEYcSLP/391)) relèvent du fournisseur d'envoi, et non du code.
- Restent ouverts : [#0390](https://trello.com/c/Jgv3udNF/390) (logo et bandeau de Fake-Léonard Industries), en attente de l'identifiant du Business Wall en production.
