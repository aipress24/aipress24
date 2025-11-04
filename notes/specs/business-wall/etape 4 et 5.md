# **Description Détaillée de l'Étape 4 : Gérer les Rôles Internes**

#### **Objectif Principal**

L'objectif de cette étape est de permettre au `Business Wall Owner` (l'utilisateur qui a activé le BW à l'étape 3) de **déléguer des droits de gestion** à d'autres membres **au sein de sa propre organisation**. Le tableau identifie deux rôles internes clés :

1.  **Business Wall Manager Interne (BWMi) :** Un co-administrateur du Business Wall.
2.  **Business Wall Press Relations Manager Interne (BWPRi) :** Un membre spécifiquement en charge des tâches de relations presse.

#### **Contexte et Point d'Entrée**

L'utilisateur est le `BW Owner`. Il accède à une interface de gestion, probablement via un menu `WORK/BUSINESS WALL/GÉRER LES MANAGERS...`.

#### **Logique Fondamentale : Un Workflow d'Invitation-Acceptation**

Le processus est un cycle de vie complet pour chaque rôle, comprenant la nomination, l'acceptation/refus par le membre, et la révocation.

**Processus de Nomination (Action de l'Owner)**

Le système doit gérer deux scénarios distincts :

*   **Scénario A : Inviter un non-membre d'AIPress24**
    1.  **Action de l'Owner :** Saisit l'adresse e-mail d'un collaborateur qui n'est pas encore inscrit sur la plateforme.
    2.  **Action du Système :** Envoie un e-mail invitant la personne à **d'abord s'inscrire sur AIPress24**. Le lien doit contenir un token d'invitation qui, une fois l'inscription terminée, présentera automatiquement à l'utilisateur l'invitation de rôle en attente.

*   **Scénario B : Nommer un membre existant d'AIPress24**
    1.  **Action de l'Owner :** Sélectionne un membre existant de son organisation dans une liste.
    2.  **Action du Système :**
        *   Envoie une **notification interne** sur la plateforme au membre sollicité.
        *   Envoie un **e-mail de notification** pour s'assurer que l'information est reçue.
        *   Affiche un message temporaire sur le BW du membre l'informant de son nouveau statut potentiel.

**Processus de Décision (Action du Membre Sollicité)**

L'utilisateur invité voit une notification dans son interface (`BUSINESS WALL/INVITATION/DEVENIR...`). Il a deux choix :

*   **Accepter la mission :**
    1.  **Action de l'Utilisateur :** Clique sur "Oui, j'accepte".
    2.  **Action du Système (Cruciale pour le RBAC) :**
        *   Le système **assigne le rôle contextuel** à l'utilisateur. Une entrée est créée/mise à jour dans la table `RoleAssignments` : `(user_id=membre, role_id=ID_DU_ROLE_BWMi_ou_BWPRi, organization_id=ID_DE_L_ORG)`.
        *   L'utilisateur est ajouté à la liste officielle des managers du BW.
        *   Il a désormais accès aux fonctionnalités permises par ce nouveau rôle.
        *   Un message de félicitations est affiché.

*   **Refuser la mission :**
    1.  **Action de l'Utilisateur :** Clique sur "Non, je refuse".
    2.  **Action du Système :** L'invitation est annulée. Aucun rôle n'est assigné. Un message de confirmation est affiché.

**Processus de Révocation (Action de l'Owner)**

1.  **Action de l'Owner :** Depuis son tableau de bord, il retire un manager de la liste.
2.  **Action du Système (Cruciale pour le RBAC) :**
    *   Le système **supprime l'entrée correspondante** dans la table `RoleAssignments`. Les droits de l'utilisateur sont immédiatement révoqués.
    *   Une notification et un e-mail sont envoyés à la personne concernée pour l'informer de la fin de sa mission.

---

# **Description Détaillée de l'Étape 5 : Gérer les Partenaires Externes (Agences RP)**

#### **Objectif Principal**

Cette étape étend le concept de délégation au-delà des murs de l'organisation. Elle permet à un `BW Owner` de **mandater une entité externe** (une agence RP ou un consultant indépendant) pour gérer ses relations presse sur AIPress24. Ce processus est basé sur un consentement mutuel et a des implications financières.

#### **Logique Fondamentale : Une Relation de Confiance Bilatérale**

Le workflow est un dialogue entre deux organisations : l'organisation "cliente" et l'organisation "prestataire" (l'agence RP).

**Processus de Mandatement (Action de l'Owner de l'organisation cliente)**

1.  **Action de l'Owner :** Depuis son menu de gestion (`WORK/BUSINESS WALL/AJOUTER DES PR AGENCIES...`), il sélectionne une agence RP existante sur AIPress24 dans une liste.
2.  **Action du Système :**
    *   Une **invitation de mandat** est envoyée à l'agence RP (à ses `BW Owners`).
    *   Le message est clair : "Nous vous invitons à devenir notre prestataire...".
    *   **Implication Financière :** Le message précise explicitement que l'acceptation ajoutera l'organisation cliente à la liste de clients de l'agence, ce qui **impacte le tarif de l'abonnement `BW for PR` de l'agence**.

**Processus de Décision (Action de l'Owner de l'agence RP)**

L'Owner de l'agence RP reçoit une notification (`WORK/BUSINESS WALL/VALIDER L’INVITATION D’UN CLIENT`).

*   **Accepter le mandat :**
    1.  **Action de l'Owner de l'agence :** Clique sur "Valider".
    2.  **Action du Système :**
        *   Une **relation formelle** est créée entre les deux organisations.
        *   Le nom de l'organisation cliente est ajouté à la liste des clients de l'agence.
        *   Le système recalcule potentiellement le tarif de l'abonnement de l'agence.
        *   **Crucial :** L'agence a maintenant le **contexte** pour assigner des rôles à ses propres employés **pour le compte de son client**. Le message de confirmation est explicite : "Nous nous réservons le choix de nos salariés qui assurerons les rôles de Business Wall Manager externe (BWMe) et de Business Wall Press Manager externe (BWPMe)".

*   **Refuser le mandat :**
    1.  **Action de l'Owner de l'agence :** Clique sur "Rejeter".
    2.  **Action du Système :** L'invitation est annulée. Une notification de refus est envoyée à l'organisation cliente.

**Processus de Délégation des Rôles Externes (Action de l'Owner de l'agence RP)**

Une fois le mandat accepté, l'Owner de l'agence peut nommer ses propres employés comme `BWMe` ou `BWPRe` pour son client. Le processus est identique à celui de l'Étape 4 (invitation/acceptation/révocation), mais avec une nuance technique majeure :

*   **Action du Système (RBAC Contextuel Avancé) :** Quand un employé de l'agence accepte le rôle de `BWMe` pour le client "Le Grand Média", une entrée est créée dans `RoleAssignments` qui lie l'employé au rôle, mais **dans le contexte de l'organisation cliente** : `(user_id=employe_agence, role_id=ID_ROLE_BWMe, organization_id=ID_DU_GRAND_MEDIA)`.

### **Synthèse et Implications**

Les étapes 4 et 5 formalisent un système de gouvernance et de délégation très puissant.

*   **Distinction Interne/Externe :** Le système fait une distinction claire entre les managers internes (employés) et externes (prestataires).
*   **RBAC Contextuel :** Tout le modèle repose sur la capacité du système RBAC à assigner des rôles à un utilisateur **pour une organisation spécifique**. Un même utilisateur peut être `PR_MANAGER` pour plusieurs organisations clientes.
*   **Workflows Complexes :** La mise en œuvre nécessite des workflows complets avec notifications, e-mails, et mises à jour de la base de données à chaque étape.
*   **Implications Financières :** L'étape 5 a un impact direct sur la facturation, ce qui requiert une communication robuste avec le système de paiement (Stripe).

Ces deux étapes sont le cœur du modèle collaboratif B2B d'AIPress24. Elles permettent de recréer les relations de travail réelles (employés, prestataires) au sein de la plateforme, avec un contrôle fin et sécurisé des permissions.
