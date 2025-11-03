# **Description Détaillée de l'Étape 1 : Confirmation de l'Abonnement**

#### **Objectif Principal**

Cette étape est le point d'entrée du parcours d'activation du Business Wall. Son but est de s'assurer que l'utilisateur s'engage dans le processus d'abonnement qui correspond précisément à la nature et aux besoins de son organisation. Elle combine une suggestion intelligente du système avec la flexibilité pour l'utilisateur de corriger ce choix.

#### **Contexte et Point d'Entrée**

L'utilisateur arrive sur cette page après avoir complété son inscription personnelle (KYC) et avoir indiqué son affiliation à une organisation. L'organisation existe à ce stade, mais son Business Wall est inactif ("non officiel").

#### **Logique Fondamentale : La Suggestion Intelligente**

*   **Source de la suggestion :** La mention "choix déjà orienté par le KYC" est la clé. Le système a analysé les réponses de l'utilisateur lors de son inscription. Par exemple :
    *   S'il a déclaré être "Journaliste en micro-entreprise", le système suggère le **"Business Wall for Micro"**.
    *   S'il a déclaré travailler pour une "PR Agency", le système suggère le **"Business Wall for PR"**.
    *   S'il est "Dirigeant" d'une entité reconnue comme un "organe de presse", le système suggère le **"Business Wall for Media"**.
*   **Mécanisme :** Le système affiche en premier lieu, et de manière proéminente, uniquement l'option d'abonnement jugée la plus pertinente.

#### **Interface Utilisateur (UI) et Expérience Utilisateur (UX)**

L'interface doit être conçue pour être claire, informative et non intimidante.

1.  **Zone de l'Abonnement Suggéré :**
    *   **Titre Clair :** "Abonnement Suggéré : [Nom du Business Wall Suggéré]".
    *   **Bloc de Messages Détaillés :** C'est l'élément le plus important. Le contenu de la colonne "Messages" doit être affiché de manière lisible, probablement sous forme de liste à puces. Chaque point doit être mis en évidence pour que l'utilisateur comprenne immédiatement :
        *   **La Proposition de Valeur :** "sera la vitrine de votre organisation...", "accès aux fonctionnalités de NEWSROOM...".
        *   **Les Actions Requises :** "vous devrez approuver notre contrat de diffusion...", "vous devez déclarer le nombre de vos salariés...".
        *   **Les Mises en Garde :** "Les informations seront vérifiées...", "un seul Business Wall par organe de presse...".
        *   **Le Modèle Économique :** La distinction entre "abonnement gratuit" et "abonnement payant" doit être visuellement évidente. Pour les abonnements payants, la mention "le tarif de votre abonnement en dépend" est cruciale.
    *   **Question d'Action Claire :** "Cet abonnement vous convient-il à votre organisation ?"
    *   **Deux Boutons d'Action Distincts :**
        *   Un bouton principal (ex: bleu ou vert) : **"Oui, confirmer cet abonnement"**.
        *   Un bouton secondaire (ex: blanc avec une bordure) : **"Non, choisir un autre abonnement"**.

2.  **Zone des Autres Abonnements (initialement cachée) :**
    *   **Déclenchement :** Cette zone n'apparaît que si l'utilisateur clique sur le bouton "Non, choisir un autre abonnement".
    *   **Présentation :** Elle doit lister tous les autres types de Business Wall disponibles. Une présentation sous forme de cartes ou de sections distinctes est idéale.
    *   **Contenu par Option :** Pour chaque option alternative, le système doit afficher :
        *   Le nom du Business Wall (ex: "Business Wall for Corporate Media").
        *   Une version condensée des messages importants qui lui sont associés.
        *   Un bouton de sélection clair : **"Choisir cet abonnement"**.

#### **Implications Techniques et Fonctionnelles Détaillées**

*   **Moteur de Règles KYC :** Un moteur de règles doit être implémenté en backend pour analyser les données du profil KYC d'un utilisateur et en déduire le `bw_type` le plus probable. Ce moteur est la base de la suggestion.
*   **Gestion de Contenu :** Les textes détaillés de la colonne "Messages" ne doivent pas être codés en dur dans les templates. Ils doivent provenir d'une source gérable (base de données, fichiers de configuration) pour pouvoir être mis à jour facilement.
*   **Gestion d'État du Workflow :** Le système doit suivre où en est l'utilisateur dans son processus d'activation. Après cette étape 1, l'état de l'utilisateur pourrait passer de `NO_BW` à `BW_TYPE_CONFIRMED` avec le type de BW choisi stocké en session ou en base de données.
*   **Front-end Interactif :** L'utilisation d'une librairie JavaScript simple (comme Alpine.js, comme dans le prototype) est nécessaire pour gérer l'affichage conditionnel de la liste des autres abonnements sans recharger la page.

#### **Analyse Spécifique des Messages par Type de BW**

*   **Pour `Media` et `Micro` :** Le message insiste sur l'**approbation d'un contrat de diffusion**, ce qui est une étape légale spécifique à ceux qui commercialisent du contenu. C'est un prérequis unique à ces deux types.
*   **Pour `Corporate Media`, `Union`, `Academics` :** L'activation est plus simple et ne requiert "que" l'approbation des CGV générales.
*   **Pour `PR`, `Leaders & Experts`, `Transformers` :** Le message introduit immédiatement la notion de **tarification dynamique**. Pour le `BW for PR`, c'est le "nombre de clients". Pour `L&E` et `Transformers`, c'est le "nombre de salariés". Cette information devra être collectée à l'étape suivante, mais l'utilisateur en est informé dès maintenant.
*   **Gestion des Délégations de RP :** Pour presque tous les types de BW (sauf `Micro` et `PR`), le message mentionne la nécessité de "déclarer et valider" les agences PR. C'est une information cruciale qui prépare l'utilisateur à la fonctionnalité de l'Étape 5.
*   **Vérification Manuelle :** Le message "Les informations que vous allez saisir seront vérifiées par les équipes d’AiPRESS24" est une constante importante. Il établit une attente claire : l'activation n'est pas entièrement automatisée et est soumise à une validation humaine, ce qui renforce la confiance et la qualité du réseau.

En conclusion, cette première étape est bien plus qu'un simple choix dans une liste. C'est un **portail d'information et d'engagement** qui pose les bases de la relation entre l'organisation et la plateforme AIPress24, en définissant les attentes, les obligations et les bénéfices de chaque type d'abonnement.
