# Changements, semaine 38 2026 (11 – 18 septembre)

La semaine compte 23 commits hors fusions, à deux (20 Jérôme, 3 Stéphane), sur 49 fichiers, plus une migration. Elle a porté deux chantiers : le signalement des commentaires, du bouton jusqu'à l'écran de modération ; et les correctifs de l'audit de sécurité de la semaine précédente.

## Signalement des commentaires

Un membre peut désormais signaler un commentaire depuis la page où il le lit. La fonction existait pour les articles ; elle couvre à présent les commentaires du Wall, puis ceux des articles et des événements, avec la même fenêtre de saisie partout.

Le code des trois surfaces a été réuni dans un service unique (`app/services/comments.py`, `app/services/moderation/alerts.py`) plutôt que recopié une troisième fois. `Comment` et `ShortPost` quittent le module SWORK pour `app.models`, où les autres modules peuvent les atteindre sans importer un module voisin.

## Modération : l'écran `/admin/content-alerts`

L'écran de traitement des signalements a été repris.

**Les signalements du même contenu sont groupés.** Dix membres signalant le même commentaire donnaient dix lignes à traiter une par une ; ils en donnent une, avec son compte.

**Un bouton « classer sans suite »** permet de clore un signalement sans supprimer le contenu, ce qui manquait : la seule issue disponible était la suppression.

**Un encart « Signalements des 90 derniers jours »** donne le contexte d'un contenu à la personne qui arbitre. Un commentaire signalé une fois et un commentaire signalé quatre fois en un trimestre ne se jugent pas de la même façon.

**Le compteur de commentaires se met à jour à la suppression.** Un commentaire supprimé pour abus laissait le compteur inchangé, si bien que la page annonçait un commentaire de plus qu'elle n'en affichait. Le recalcul est passé dans le service, avec les tests correspondants.

## Sécurité

Les cinq correctifs de l'audit de la semaine dernière sont livrés. Le détail figure dans `notes/security/report-2026-09-17.md` ; en résumé de ce qui change pour la plateforme :

**La console d'administration `/db/` n'est plus montée.** Elle donnait à tout visiteur anonyme la lecture et l'écriture sur les utilisateurs, les profils KYC et les contenus, sans authentification, dans le processus de production. Elle demande maintenant une variable explicite pour exister.

**Un journaliste ne peut plus répondre à l'avis d'enquête d'un autre.** Il pouvait le faire en connaissant l'identifiant, et l'email d'acceptation partait sous l'identité de la plateforme. Les 88 chemins d'écriture de l'application ont été balayés pour vérifier que celui-ci était le seul.

**Les mots de passe d'inscription sont hachés.** Ils étaient stockés tels que saisis, ce qui les exposait dans chaque sauvegarde et empêchait aussi ces comptes de se connecter. Les valeurs déjà écrites ont été effacées par migration : leurs titulaires passent par la récupération de mot de passe.

**Le mode `UNSECURE` ne peut plus arriver en production sans bruit.** Il ouvre une route qui rend une session administrateur à un visiteur anonyme, et une autre qui imprime tous les secrets du processus. La section production le désactive, le démarrage refuse la combinaison, et un serveur lancé par erreur dans cet état l'inscrit dans ses journaux.

**Le serveur HTTP passe de granian 1.7.6 à 2.8.3**, ce qui ferme deux dénis de service non authentifiés.

**Et l'écran de modification KYC vérifie qui le demande.** Un visiteur anonyme pouvait poser en session le drapeau qui fait passer le formulaire en mode édition, lequel retire le champ mot de passe. Le drapeau ne produit plus d'effet que pour un utilisateur authentifié. Ce point avait été relevé en vérifiant le correctif sur les mots de passe, dont il était la condition d'atteignabilité.

## Tests

Seize fichiers de tests ont été touchés, pour un peu plus de mille lignes ajoutées. Le signalement des commentaires, le bouton « classer sans suite », le recalcul du compteur et la modification KYC portent chacun les leurs ; les correctifs de sécurité étaient arrivés avec les leurs la semaine précédente.

## Bugs fermés

Aucun ticket utilisateur n'a été cité cette semaine. Le travail vient des retours de l'audit et du chantier de modération.

## À savoir

- Deux actions restent à faire hors du code, et aucun correctif ne les remplace : **révoquer la clé Stripe de test** présente dans l'historique du dépôt, et **changer la clé de signature** qui figure dans les réglages de développement.
- Si la console `/db/` servait à quelqu'un, elle demande maintenant `DB_ADMIN_ENABLED` pour être montée. L'activer revient à rouvrir une porte sans serrure ; il vaut mieux lui donner une authentification d'abord.
- La production doit poser `ENV_FOR_DYNACONF=production`. Sans cette variable, la configuration résout l'environnement de développement, avec les réglages permissifs qui vont avec.
