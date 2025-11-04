# **Description Détaillée de l'Étape 7 : Configuration du Business Wall**

#### **Objectif Principal**

L'objectif de cette étape est de permettre aux gestionnaires du Business Wall de **renseigner et de maintenir à jour toutes les informations** qui décrivent leur organisation. C'est l'équivalent de la page "Modifier mon profil" pour une organisation.

#### **Logique Fondamentale : Un Formulaire Dynamique et Adaptatif**

La clé de cette étape est que le formulaire n'est pas monolithique. Il est intelligemment conçu pour ne présenter que les champs pertinents pour le type d'organisation concernée.

*   **Structure du Formulaire :** Le formulaire est divisé en sections logiques (Graphisme, Informations Administratives, Description de l'activité, Contact).
*   **Affichage Conditionnel :** Les colonnes `BW4Media`, `BW4jMicro`, etc., indiquent quels champs sont applicables à quel type de BW. Un "o" signifie que le champ doit être affiché.
    *   *Exemple :* Le champ "Si vous opérez une micro-entreprise de presse, saisissez son nom" n'apparaîtra **que** si l'utilisateur configure un `BW4jMicro`.
    *   *Exemple :* La section "CONFIGURATION POUR LES PR AGENCIES & PR INDEPS" n'apparaîtra **que** pour un `BW for PR`.

#### **Interface Utilisateur (UI) Détaillée**

L'interface sera un long formulaire, mais présenté de manière structurée avec des sections claires et des aides contextuelles.

**Section 1 : `GRAPHISME` (Commune à tous)**
*   **Champs :** Trois champs de téléversement (`upload`) de fichiers.
    *   Logo de l'organisation.
    *   Bandeau du Business Wall (image de couverture).
    *   Galerie d'images (avec une référence au module de carrousel existant, ce qui est une excellente pratique de réutilisation de composants).
*   **UX :** L'interface doit permettre de prévisualiser les images et de les remplacer facilement.

**Section 2 : `CONFIGURATION POUR LES ORGANES DE PRESSE` (pour `Media`, `jMicro`, `cMedia`, `pUnion`)**
*   **Sous-section `INFORMATIONS ADMINISTRATIVES` :**
    *   Champs de texte pour les informations légales (nom, SIREN, TVA).
    *   **Logique Complexe :** Plusieurs champs (nom du groupe, nom de la société éditrice) sont liés à la "liste officielle des organisations abonnées". Cela implique une fonctionnalité d'**auto-complétion** ou de recherche pour lier l'entité à une autre déjà existante dans la base de données.
    *   **Action Juridique :** Un champ pour approuver l'**accord de distribution**, avec un lien vers le document. L'acceptation doit être enregistrée.
*   **Sous-section `DÉCRIVEZ L’ACTIVITÉ` :**
    *   Une série de champs basés sur des **ontologies** (listes de choix prédéfinies) : "Type de presse", "Périodicité", "Secteurs d'activités", etc.
    *   Des champs de texte libre avec des contraintes de longueur (ex: "Positionnement éditorial", max 500 signes).
*   **Sous-section `COMMENT NOUS CONTACTER` :**
    *   **Logique Complexe :** Des champs pour désigner les `BWPRi` (internes) et `BWPRe` (externes). Cela implique une interface de **sélection d'utilisateurs** (pour les internes) et de **sélection d'organisations partenaires** (pour les externes) qui ont déjà été validées à l'Étape 5.
    *   Champs de contact classiques (téléphone, adresse, URL, géolocalisation).

**Sections 3, 4, 5, 6 : `CONFIGURATION POUR PR`, `LEADERS & EXPERTS`, `TRANSFORMERS`, `ACADEMICS`**
*   Ces sections suivent la même structure (Infos Admin, Description, Contact), mais avec des champs spécifiquement adaptés :
    *   **Pour `PR` :** Un champ crucial pour "Ajouter vos clients", qui doit être une liste dynamique où l'on peut sélectionner les organisations clientes (celles qui ont validé le mandat à l'Étape 5).
    *   **Pour `Transformers` :** Un champ spécifique "Quelles sont les grandes transformations..." basé sur l'ontologie `Transf. Maj.`.
    *   Les autres champs sont des variations de ceux vus précédemment, toujours en s'appuyant sur des ontologies pour standardiser les données.

#### **Implications Techniques et Fonctionnelles**

*   **Formulaire Dynamique Côté Front-end :** C'est le défi principal. L'interface doit être construite avec une logique d'affichage conditionnel puissante (probablement en JavaScript/Alpine.js) qui montre/cache des dizaines de champs en fonction du `bw_type` de l'organisation en cours d'édition.

*   **Connexion aux Ontologies :** Tous les champs marqués "ONTOLOGIES/..." doivent être implémentés comme des listes déroulantes (`select`), des sélecteurs multiples (`multi-select`) ou des champs d'auto-complétion qui chargent leurs options depuis la base de données des taxonomies.

*   **Widgets d'Interface Complexes :** Plusieurs champs nécessitent des composants spécifiques :
    *   Un gestionnaire de galerie d'images.
    *   Un sélecteur d'utilisateurs avec recherche (pour les contacts internes).
    *   Un sélecteur d'organisations avec recherche (pour les clients et partenaires externes).
    *   Un module de géolocalisation avec auto-complétion pour les adresses.

*   **Validation des Données :** Le backend doit valider rigoureusement les données soumises, en s'assurant par exemple qu'un `BW for Media` ne remplit pas des champs réservés à un `BW for PR`.

*   **Persistance des Données :** Toutes ces informations doivent être stockées dans le modèle `Organization` en base de données. Le modèle devra donc être assez large pour contenir tous les champs possibles, beaucoup d'entre eux étant optionnels (`nullable`).

### **Synthèse**

L'Étape 7 est la phase de **personnalisation et d'enrichissement des données** du Business Wall. Elle transforme une coquille vide en une page de profil riche et informative pour l'organisation.

La réussite de cette étape repose sur la capacité à construire un **formulaire hautement dynamique et intelligent**, qui guide l'utilisateur en ne lui présentant que les informations pertinentes pour son cas d'usage, tout en s'appuyant sur des données structurées (ontologies) pour garantir la qualité et la cohérence des informations sur toute la plateforme. C'est un travail de développement front-end et back-end conséquent qui finalise la création de la "vitrine" de l'organisation.
