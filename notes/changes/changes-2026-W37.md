# Changements, semaine 37 2026 (7 – 11 septembre)

46 commits hors fusions, 117 fichiers, une migration. Cinq tickets remontés par les utilisatrices, un audit de sécurité, et le travail d'affichage des sélecteurs qui traîne depuis le changement de taxonomies.

## KYC et inscription

Après un changement de taxonomie, rouvrir son profil affichait les anciennes valeurs puis refusait de les enregistrer, sans dire lesquelles. La règle devient : les valeurs de la taxonomie courante, **plus** celles que le profil portait déjà. Un terme retiré reste impossible à choisir, mais on n'est plus bloqué par un choix qu'on n'a pas fait. ([#0333](https://trello.com/c/Nntlrpgt/333))

Cette correction a cassé l'inscription pendant une journée — erreur serveur pour tout nouvel arrivant. Corrigée le lendemain, avec le test qui manquait sur ce chemin.

## Sélecteurs et saisie

Les listes déroulantes riches tronquaient leurs options et la saisie rapprochait des valeurs sans rapport. Elles affichent la liste complète, la frappe resserre au lieu d'élargir, et le tri ignore les accents : « Éducation » ne se classe plus après « Zoologie ». Le composant est servi depuis la plateforme, plus depuis un service extérieur.

## Newsroom — commandes

Une commande née d'un sujet accepté annonçait « Commande adressée à » suivi du nom de votre propre agence. L'écran nomme désormais trois rôles : à qui la commande s'adresse — le journaliste qui l'écrira —, qui l'a commandée, et le média concerné. Les deux premiers n'apparaissaient nulle part. ([#0353](https://trello.com/c/Mc63INFr/353))

La date de paiement quitte le formulaire : « je connais la date de bouclage et de publication, mais je ne peux pas donner de date de paiement ». Les commandes qui en portent déjà une la gardent. ([#0343](https://trello.com/c/jxA3YQgK/343))

## Newsroom — avis d'enquête et ciblage

Une case « Inclure des journalistes dans la sélection » a été ajoutée, et l'ordre des filtres corrigé : l'exclusion des journalistes s'applique désormais **avant** le filtre thématique. Sur un secteur où les journalistes dominent, décocher la case vidait le vivier entièrement. ([#0344](https://trello.com/c/OYNMcZJp/344))

Les critères de ciblage ne suivent plus l'utilisateur suivant : sur un poste partagé, la personne qui se connectait après vous héritait de vos filtres, et un ciblage filtré sur les critères d'un autre n'affiche personne sans rien dire.

## Événements

Le formulaire ne plante plus à la modification — deux formats de date se contredisaient, et les valeurs de « mode » et de « tarif » ne faisaient pas l'aller-retour. Le bandeau change de couleur, et le refus d'accréditation s'annonce plus sobrement : « Nous sommes désolés de… ».

## Images et paiements

Photos de profil, logos et pièces jointes étaient servis par des adresses signées à durée limitée : passé le délai, l'image cassait. Elles passent par une adresse stable, calculée sur le contenu, et un réglage de signature S3 manquant est corrigé.

La page de règlement Stripe ne s'ouvrait pas : la politique de sécurité du navigateur ne l'autorisait pas. Réglé.

## Sécurité

Audit de la surface exposée — écrans, paiement, téléversements, KYC, API, authentification — chaque constat soumis à une contre-expertise. Sur cinq candidats : deux confirmés et corrigés, deux réfutés, un retiré.

**Un journaliste pouvait lire et réécrire l'avis d'enquête d'un autre**, en connaissant son identifiant — que la plateforme montre à toute personne sollicitée. L'écran de ciblage était atteignable de même (noms, photos, fonctions, organisations des experts visés), et l'on pouvait publier l'avis et solliciter ces personnes **au nom de son propriétaire**. La règle qui protège les listes ne s'appliquait pas à l'ouverture directe par identifiant ; elle vaut maintenant partout dans l'espace de travail.

**Un fichier téléversé décidait du type sous lequel il serait servi.** Le nommer `.svg` ou `.html` donnait du code exécutable servi depuis le domaine de la plateforme, contre la session de qui l'ouvrait. Deux verrous, dont un qui couvre les fichiers déjà stockés.

Le modèle de menace est écrit et relu — adversaires, ce qu'ils atteignent, ce qui est hors périmètre. Il vit dans `notes/security/` avec le rapport.

## Tests

Une trentaine de fichiers touchés. Les deux correctifs de sécurité, celui du ciblage et celui de l'inscription portent chacun un test vérifié : il échoue sans le correctif. Un enseignement au passage — un test qui cherche l'absence d'un message d'erreur passe aussi contre une page en erreur.

## Bugs fermés

[#0333](https://trello.com/c/Nntlrpgt/333), [#0343](https://trello.com/c/jxA3YQgK/343), [#0344](https://trello.com/c/OYNMcZJp/344), [#0353](https://trello.com/c/Mc63INFr/353).

## À savoir

- **#0348 — « aucun contact quel que soit le secteur » : non reproduit.** Un script de diagnostic est livré, à lancer sur la base où le problème se voit ; il n'affiche que des comptes. À connaître : **19 des 858 valeurs de secteur portées par les profils existent telles quelles dans la taxonomie courante**. Le reste ne tient que par le code de compatibilité — qui fonctionne ici (93 %), mais c'est un filet, pas un sol.
- Un refus d'accès dans l'espace de travail répond « page introuvable » là où certains écrans redirigeaient vers l'accueil. Délibéré : une redirection confirmait que l'identifiant existait.
- Chantier ouvert que l'audit n'a pas traité : la politique de sécurité du navigateur autorise le script en ligne, ce qui amplifie toute faille d'injection.
- Si le jeton de déploiement Fly a été créé dans les réglages GitHub, il reste à révoquer. Le workflow qui le nommait n'a jamais été dans le dépôt.
