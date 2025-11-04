# **Description Détaillée de l'Étape 6 : Missions à Attribuer**

#### **Objectif Principal**

L'objectif de cette étape est de fournir une interface simple et intuitive au `BW Owner` (ou à un `BW Manager` délégué) pour **accorder ou révoquer des droits de publication granulaires** aux `PR Managers` (qu'ils soient internes ou externes à l'organisation). Chaque "mission" correspond à une permission spécifique.

#### **Contexte et Point d'Entrée**

L'utilisateur (le `BW Owner` ou un `BW Manager`) est connecté au Business Wall de son organisation. Il accède à cette interface via un menu spécifique : `MENU : WORK/BUSINESS WALL/AJOUTER DES MISSIONS AUX BWPRMi`.
*   La désignation "BWPRMi" (Press Relations Managers Internes) dans le titre du menu suggère que cette page pourrait être la même pour les PR Managers internes et externes, car le tableau mentionne "PR Managers Internes OU Externes".

#### **Logique Fondamentale : Interrupteurs de Permissions**

Le cœur de cette interface est une liste de fonctionnalités (les "Missions") pour lesquelles le `BW Owner` peut simplement cocher "Oui" ou "Non".

*   **"Éléments" :** Chaque ligne représente une catégorie de publication (Communiqués de presse, Événements, Missions, Projets, Offres de stage, Offres d'alternance, Offres de convention doctorale).
*   **"Actions" :** La colonne "Oui/Non" est un interrupteur.
    *   **Passer de "Non" à "Oui" :** L'Owner accorde la mission. Le système doit ajouter la permission correspondante au rôle `PR_MANAGER` (dans le contexte de l'organisation).
    *   **Passer de "Oui" à "Non" :** L'Owner retire la mission. Le système doit retirer la permission correspondante du rôle `PR_MANAGER`.
*   **"Messages" :** Chaque ligne fournit un message de confirmation simple qui explique la conséquence de l'activation de la mission. Par exemple, si la mission "Publier les communiqués de presse" est activée, le message indique que "Ces communiqués apparaîtront sur le Portail NEWS/Idées & Com' d’AiPRESS24, sur le Business Wall de votre organisation et sur votre profil personnel."

#### **Interface Utilisateur (UI) Détaillée**

L'interface sera un formulaire listant les missions, chacune avec un sélecteur "Oui/Non".

*   **Titre de la Page :** "6- MISSIONS À ATTRIBUER"
*   **Introduction :** Un court texte expliquant que cette page permet d'autoriser les PR Managers à publier des contenus spécifiques au nom de l'organisation.
*   **Liste des Missions (Permissions) :** Chaque mission est présentée sur une ligne distincte.
    *   **Libellé de la Mission :** (Ex: "Sous-menu : /Publier les communiqués de presse")
    *   **Contrôle "Oui/Non" :** Un bouton radio ou un interrupteur (`toggle switch`) visuellement clair.
    *   **Description de l'Impact :** Le message correspondant à la mission, expliquant où le contenu sera visible (NEWS, EVENTS, MARKET, profil personnel, BW de l'organisation).

**Exemples de Permissions et leurs Impacts (tels que traduits pour le système) :**

1.  **`/Publier les communiqués de presse`**
    *   **Permission :** `'press_release:create'` (pour cette organisation).
    *   **Impact :** Donne le droit de créer et de publier des CP. Les CP seront visibles sur le Portail NEWS, le BW de l'organisation et le profil du PR Manager.

2.  **`/Publier des événements`**
    *   **Permission :** `'event:manage'` (pour cette organisation).
    *   **Impact :** Donne le droit de créer et de publier des événements. Visibilité sur l'espace EVENTS et le BW de l'organisation.

3.  **`/Publier des Missions`**
    *   **Permission :** `'mission:create'` (pour cette organisation).
    *   **Impact :** Donne le droit de publier des offres de mission sur la Marketplace. Visibilité sur MARKET/Missions et le BW de l'organisation.

4.  **`/Publier des Projets`**
    *   **Permission :** `'project:create'` (pour cette organisation).
    *   **Impact :** Donne le droit de publier des projets. Visibilité sur MARKET/Projets et le BW de l'organisation.

5.  **`/Publier des offres de stage`**
    *   **Permission :** `'internship:offer'` (pour cette organisation).
    *   **Impact :** Donne le droit de publier des offres de stage sur le Job Board. Visibilité sur MARKET/Job Board et le BW de l'organisation.

6.  **`/Publier des offres d’alternance`**
    *   **Permission :** `'apprenticeship:offer'` (pour cette organisation).
    *   **Impact :** Donne le droit de publier des offres d'alternance. Visibilité sur MARKET/Job Board et le BW de l'organisation.

7.  **`/Publier des Offres de convention doctorale`**
    *   **Permission :** `'doctoral_agreement:offer'` (pour cette organisation).
    *   **Impact :** Donne le droit de publier des offres de convention doctorale. Visibilité sur MARKET/Job Board et le BW de l'organisation.

**Bouton de Soumission :** Un bouton clair "Enregistrer les modifications" pour sauvegarder les choix.

#### **Implications Techniques et Fonctionnelles (RBAC en action)**

*   **Point d'Accès Sécurisé :** Seul un utilisateur avec la permission `bw:manage_pr_roles` (ou `bw:manage_internal_roles`) pour cette organisation devrait pouvoir accéder à cette page.
*   **Manipulation de la `Role_Permissions` Contextuelle :**
    *   Lorsque l'Owner active une mission (passe à "Oui"), le système doit ajouter la permission correspondante (ex: `'press_release:create'`) au rôle `PR_MANAGER`.
    *   Lorsque l'Owner désactive une mission (passe à "Non"), le système doit retirer cette permission du rôle `PR_MANAGER`.
    *   **Crucial :** Cette modification n'est pas faite directement sur la table `auth_role_permissions` (qui définit ce que le rôle `PR_MANAGER` peut faire en général), mais elle doit être réfléchie pour s'appliquer **contextuellement à cette organisation et à ce rôle délégué**. Cela pourrait impliquer de modifier la façon dont `get_permissions()` agrège les droits, ou de créer un rôle plus spécifique `PR_MANAGER_O1` dynamique pour l'organisation `O1`.
*   **Dynamisme :** L'état des interrupteurs ("Oui" ou "Non") doit refléter l'état actuel des permissions attribuées au rôle `PR_MANAGER` pour cette organisation.

En résumé, l'Étape 6 est la matérialisation de la gestion fine des droits que vous souhaitiez. C'est une interface conviviale pour des actions complexes sur le backend RBAC, permettant aux organisations de contrôler précisément ce que leurs délégués peuvent publier.
