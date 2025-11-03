# **Description Globale du Processus de Création et de Configuration du Business Wall**

Le processus de création et de gestion d'un Business Wall (BW) sur AIPress24 est un parcours d'onboarding structuré en 7 étapes séquentielles. Il vise à guider chaque type d'organisation (média, agence RP, entreprise, etc.) depuis son inscription jusqu'à une gestion fine et déléguée de sa présence et de ses activités sur la plateforme. Ce workflow transforme une simple "fiche d'organisation" en un véritable extranet collaboratif et transactionnel.

#### **Vue d'Ensemble du Parcours en 7 Étapes**

1.  **Confirmation de l'Abonnement :** L'utilisateur valide le type de BW que le système lui a suggéré sur la base de son profil KYC, ou en choisit un autre plus adapté.
2.  **Nomination des Responsables :** L'utilisateur désigne les contacts légaux et financiers clés : le `Business Wall Owner` (décisionnaire) et la `Paying Party` (contact facturation).
3.  **Activation du Compte :** Le cœur du processus, où l'utilisateur finalise l'activation soit par l'acceptation de conditions légales (pour les BW gratuits), soit par un paiement (pour les BW payants). Cette étape lui confère le rôle de `BW Owner`.
4.  **Gestion des Rôles Internes :** Une fois `Owner`, l'utilisateur peut inviter et nommer des `Business Wall Managers` (BWMi) et des `Press Relations Managers` (BWPRi) au sein de son organisation. Un workflow complet d'invitation/acceptation/révocation est mis en place.
5.  **Gestion des Partenaires Externes :** Le `BW Owner` peut mandater des agences RP externes (`PR Agencies` ou `PR Indeps`) pour le représenter, initiant un cycle de validation mutuelle qui affecte la facturation de l'agence.
6.  **Attribution des Missions :** Le `BW Owner` (ou un `Manager` délégué) peut attribuer des permissions granulaires ("missions") aux `PR Managers` (internes ou externes), leur donnant le droit de publier des communiqués, événements, offres d'emploi, etc., au nom de l'organisation.
7.  **Configuration du Contenu du BW :** Enfin, le `BW Owner` ou ses `Managers` peuvent remplir le contenu public de leur Business Wall (logo, description, contacts, etc.) via un formulaire dynamique dont les champs s'adaptent au type de BW.

---

### **Détail des Étapes Clés et de leur Logique**

*   **Étape 1 : Confirmation Intelligente**
    Le système ne part pas de zéro. Il utilise les données de l'inscription (KYC) pour proposer un type d'abonnement pertinent. L'utilisateur est informé en détail des bénéfices et des obligations de chaque abonnement, lui permettant de faire un choix éclairé.

*   **Étape 2 : Séparation des Rôles de Gouvernance**
    Le processus distingue clairement le responsable légal (`Owner`) du contact de facturation (`Paying Party`), ce qui est une pratique professionnelle essentielle. Le système facilite la saisie en pré-remplissant les informations avec celles de l'utilisateur courant.

*   **Étape 3 : Activation et Assignation du Rôle Clé**
    C'est le point de bascule. L'activation, qu'elle soit juridique (CGV) ou financière (Stripe), transforme le statut de l'organisation et confère à l'utilisateur le rôle pivot de **`BW Owner`**. Ce rôle lui donne les méta-permissions nécessaires pour gérer toutes les étapes suivantes. Pour les BW payants, cette étape est précédée par la saisie d'informations déterminant le tarif (nombre de clients/salariés), introduisant une logique de facturation dynamique.

*   **Étapes 4 & 5 : Un Système de Délégation à Double Niveau**
    Ces étapes implémentent une gouvernance sophistiquée :
    1.  **Délégation Interne (Étape 4) :** L'Owner peut nommer des managers au sein de sa propre équipe.
    2.  **Délégation Externe (Étape 5) :** L'Owner peut mandater une entité externe (une agence RP). Ce processus est sécurisé par une validation mutuelle : l'agence doit accepter le mandat, et cette acceptation a un impact direct sur sa propre facturation, créant un cercle de confiance et de responsabilité.

*   **Étape 6 : Contrôle d'Accès Granulaire (RBAC en action)**
    C'est l'implémentation pratique de notre modèle RBAC. Le `BW Owner/Manager` utilise une interface simple (des interrupteurs Oui/Non) pour accorder des permissions spécifiques (`press_release:create`, `event:manage`, etc.) au rôle de `PR Manager`. Il ne manipule pas des rôles complexes, mais des "missions" compréhensibles.

*   **Étape 7 : Personnalisation de la Vitrine Publique**
    La dernière étape est la configuration du contenu visible du Business Wall. Le formulaire est intelligent : il ne présente à l'utilisateur que les champs pertinents pour son type d'organisation, évitant ainsi la confusion et garantissant la collecte des bonnes informations (par exemple, seul un média se verra demander son positionnement éditorial).

### **Conclusion**

Ce processus en 7 étapes est bien plus qu'une simple inscription. C'est un **workflow d'onboarding et de gouvernance complet** qui transforme une organisation en un acteur à part entière de l'écosystème AIPress24. Il établit clairement les responsabilités, met en place un système de délégation sécurisé, et donne aux administrateurs les outils pour gérer finement les droits de publication, le tout en s'appuyant sur un modèle de permissions robuste et évolutif.


### Références

#### Etape 1
- etape 1.md
- etape 1 - table.md

#### Etape 2
- etape 2.md
- etape 2 - table.md

#### Etape 3
- etape 3.md
- etape 3 - table.md

#### Etape 4 et 5
- etape 4 et 5.md
- etape 4 - table.md
- etape 5 - table.md

#### Etape 6
- etape 6.md
- etape 6 - table.md

#### Etape 7
- etape 7.md
- etape 7 - table.md
