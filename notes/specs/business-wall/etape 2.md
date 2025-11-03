# **Description Détaillée de l'Étape 2 : Nomination des Responsables**

#### **Objectif Principal**

L'objectif de cette étape est de **formaliser la gouvernance** du futur Business Wall en identifiant deux rôles de responsabilité distincts et obligatoires :

1.  **Le Business Wall Owner (OWNER) :** Il s'agit du **responsable légal et décisionnaire** de l'abonnement au sein de l'organisation. C'est le contact principal pour toute communication stratégique ou légale de la part d'AIPress24.
2.  **La Business Wall Paying Party :** Il s'agit du **contact pour la facturation**. C'est à cette personne (ou ce service) que les factures et les communications relatives au paiement seront envoyées.

Cette séparation est une pratique professionnelle standard qui reconnaît que le décisionnaire n'est pas toujours la personne en charge des paiements (ex: un Directeur de la Communication vs. le Service Comptabilité).

#### **Logique Fondamentale et Expérience Utilisateur (UX)**

Le formulaire doit être conçu pour être à la fois rigoureux dans la collecte d'informations et simple à remplir pour l'utilisateur.

1.  **Pré-remplissage Intelligent :**
    *   L'utilisateur qui effectue ce processus est, par définition, le candidat le plus probable pour être le `Business Wall Owner`.
    *   **Action UX :** Le formulaire pour le `BW Owner` doit être **automatiquement pré-rempli** avec les informations du profil de l'utilisateur actuellement connecté (Nom, Prénom, E-mail, Téléphone).
    *   **Bénéfice :** L'utilisateur n'a qu'à vérifier et valider ces informations, ce qui réduit considérablement la friction. Il peut bien sûr les modifier s'il agit au nom de quelqu'un d'autre (par exemple, un assistant pour son directeur).

2.  **Gestion de la "Paying Party" :**
    *   **Règle Métier Clé :** "Cette personne n’est pas obligatoirement membre d’AiPRESS24." C'est une information cruciale qui implique que les champs pour ce contact doivent être entièrement libres.
    *   **Action UX :** Pour simplifier la saisie dans le cas le plus courant (où l'Owner est aussi le contact de facturation), une case à cocher est indispensable : **"Les coordonnées du payeur sont les mêmes que celles du dirigeant (Owner)"**.
    *   **Comportement :**
        *   Si la case est cochée (état par défaut), le formulaire pour la `Paying Party` est masqué ou désactivé.
        *   Si la case est décochée, le formulaire apparaît, permettant à l'utilisateur de saisir des coordonnées distinctes.

#### **Interface Utilisateur (UI) Détaillée**

L'interface doit être un formulaire unique, clairement structuré en deux sections.

*   **Titre de la Page :** "2- Nommer vos contacts responsables"
*   **Introduction :** Un court texte expliquant l'importance de cette étape.

**Section 1 : Business Wall Owner**
*   **Titre de Section :** "Dirigeant Décisionnaire (Owner)"
*   **Message d'Aide :** "Renseignez/Modifiez les coordonnées du dirigeant décisionnaire (OWNER) responsable de l’abonnement de votre organisation à Business Wall."
*   **Champs du Formulaire (pré-remplis) :**
    *   Prénom (champ texte, requis)
    *   Nom (champ texte, requis)
    *   Fonction/Titre (champ texte, optionnel)
    *   Adresse e-mail (champ e-mail, requis, validé)
    *   Téléphone (champ texte, optionnel)

**Section 2 : Contact de Facturation (Paying Party)**
*   **Titre de Section :** "Contact pour la Facturation"
*   **Message d'Aide :** "Renseignez/Modifiez les coordonnées du payeur de l’abonnement (Nom, coordonnées du payeur). Cette personne n’est pas obligatoirement membre d’AiPRESS24."
*   **Case à Cocher :** [x] Les coordonnées du payeur sont les mêmes que celles du dirigeant (Owner).
*   **Champs du Formulaire (conditionnels) :**
    *   Prénom (champ texte, requis si la case est décochée)
    *   Nom (champ texte, requis si la case est décochée)
    *   Service (ex: "Service Comptabilité", champ texte, optionnel)
    *   Adresse e-mail de facturation (champ e-mail, requis si la case est décochée, validé)
    *   Téléphone (champ texte, optionnel)
    *   Adresse de facturation (si différente, champ texte multi-lignes, optionnel)

**Navigation du Formulaire :**
*   **Bouton "Retour" :** Permet de revenir à l'Étape 1 pour changer le type d'abonnement.
*   **Bouton "Continuer" :** Soumet le formulaire. Ce bouton ne devrait être actif que lorsque tous les champs requis des sections visibles sont remplis.

#### **Implications Techniques et Fonctionnelles**

*   **Stockage des Données :** Ces informations doivent être stockées de manière sécurisée, probablement dans des champs dédiés sur le modèle `Organization`. Par exemple : `owner_contact_name`, `owner_contact_email`, `payer_contact_name`, `payer_contact_email`, etc.
*   **Validation Backend :** Le serveur doit valider que toutes les informations requises ont été soumises avant de permettre à l'utilisateur de passer à l'étape 3.
*   **Lien avec le Rôle `Owner` :** Bien que ce formulaire identifie le *contact* Owner, c'est l'Étape 3 qui assignera techniquement le **rôle** `BW_OWNER` à l'utilisateur qui **effectue l'action d'activation**. Ce formulaire sert principalement à des fins administratives et de communication.
*   **Intégration avec Stripe :** L'adresse e-mail du `Paying Party` sera probablement celle qui sera passée à Stripe en tant que `customer_email` lors de la création de l'abonnement pour les BW payants.

En résumé, l'Étape 2 est une étape administrative formelle qui solidifie la relation entre l'organisation cliente et AIPress24. Elle garantit que les bons interlocuteurs sont identifiés pour les aspects légaux et financiers, tout en étant conçue pour être la plus fluide possible pour l'utilisateur final grâce à une UX bien pensée (pré-remplissage et duplication des données).
