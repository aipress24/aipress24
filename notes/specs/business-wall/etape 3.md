# **Description Détaillée de l'Étape 3 : Activation du Business Wall**

#### **Objectif Principal**

L'objectif de cette étape est de **finaliser l'activation du Business Wall**. Pour l'utilisateur, cela se traduit par une action de confirmation finale. Pour le système, cela déclenche une série d'actions cruciales : la mise à jour du statut de l'organisation, l'attribution du rôle de propriétaire (`Owner`), et l'envoi de communications de bienvenue.

#### **Logique Fondamentale : Deux Parcours d'Activation Distincts**

Le workflow se divise ici en deux branches, basées sur le choix fait à l'Étape 1.

**Parcours A : Activation d'un Business Wall GRATUIT**
*   **Concerne :** `Media`, `Micro`, `Corporate Media`, `Union`, `Academics`.
*   **Action Utilisateur Requise :** Une confirmation légale. L'utilisateur doit activement approuver des documents.
    *   **Pour `Media` et `Micro` :** C'est une double approbation : l'**Accord de diffusion** (spécifique à la vente de contenu) ET les **CGV générales** du Business Wall.
    *   **Pour les autres (Corporate, Union, Academics) :** C'est une approbation unique des **CGV générales** du Business Wall.
*   **Interface (UI) :** L'interface doit présenter clairement les documents à approuver (avec des liens pour les consulter) et une case à cocher ou un bouton explicite comme "J'accepte les conditions et j'active mon Business Wall".

**Parcours B : Activation d'un Business Wall PAYANT**
*   **Concerne :** `PR`, `Leaders & Experts`, `Transformers`.
*   **Logique en deux temps :**
    1.  **Saisie des Métriques de Tarification (Pré-paiement) :** Comme spécifié, l'utilisateur doit d'abord fournir une donnée qui conditionne le prix. L'interface doit présenter un champ numérique clair :
        *   Pour `BW for PR` : "Nombre de clients représentés sur AIPress24".
        *   Pour `BW for L&E` et `BW for Transformers` : "Nombre de salariés de votre organisation".
        *   Le message explicatif "Ce nombre... détermine dynamiquement le tarif de votre abonnement" est essentiel pour la transparence.
    2.  **Paiement sur Stripe (Action finale) :** Après la saisie de la métrique, l'action finale est le paiement. L'interface doit présenter un bouton "Payer et Activer via Stripe" qui redirige l'utilisateur vers la page de paiement Stripe préconfigurée avec le bon tarif.

#### **Conséquences Systèmes Communes à Tous les Parcours**

Quelle que soit la méthode d'activation, le tableau spécifie trois conséquences techniques identiques et critiques qui doivent être déclenchées par le système une fois l'action de l'utilisateur réussie (approbation légale ou paiement confirmé).

1.  **"Activer le Business Wall de cette organisation" :**
    *   **Action Technique :** Dans la base de données, le statut de l'objet `Organization` doit changer. Par exemple, le champ `is_active` passe à `True` et le champ `bw_type` est définitivement fixé.

2.  **"Celui-ci est rajouté à la liste des Business Wall..." :**
    *   **Action Technique :** L'organisation devient publiquement visible et découvrable. Elle apparaît désormais dans les annuaires, les résultats de recherche, etc., en tant qu'entité officielle avec un Business Wall actif.

3.  **"La personne qui active... est « OWNER »" :**
    *   **Action Technique (Cruciale pour le RBAC) :** Le système doit **assigner le rôle `BW_OWNER`** (ou `BW_MANAGER` dans notre modèle) à l'utilisateur actuellement connecté, et ce, dans le contexte de cette organisation. Concrètement, une nouvelle entrée est créée dans la table `RoleAssignments` : `(user_id=current_user.id, role_id=ID_DU_ROLE_OWNER, organization_id=current_org.id)`. C'est cet événement qui lui donne les droits pour accéder aux étapes 4, 5, 6 et 7.

#### **Messages de Confirmation**

Une fois l'activation réussie, le système doit afficher un message de confirmation clair et engageant.

*   **Contenu du Message :**
    *   **Félicitations :** "Vous venez d’activer le Business Wall... Nous vous en félicitons."
    *   **Confirmation du Statut :** "Vous êtes à présent « Business Wall Owner » de votre abonnement."
    *   **Appel à l'Action (Call to Action) :** C'est la partie la plus importante pour la suite du parcours. Le message doit immédiatement guider l'Owner vers sa prochaine tâche : **"Pour le gérer, nous vous invitons à désigner vos Business Wall Managers internes ou externes ainsi que vos Business Wall PR Managers..."**.
*   **Interface (UI) :** Ce message devrait apparaître sur une page de succès dédiée, avec un bouton proéminent comme "Accéder à la gestion de mon Business Wall", qui redirige l'utilisateur vers le tableau de bord de l'Étape 4.

### **Synthèse des Implications**

L'Étape 3 est le point de non-retour du processus. Elle formalise la relation contractuelle et technique entre l'organisation et AIPress24.

*   **Pour l'utilisateur,** c'est l'action finale de validation, qui doit être simple et sans ambiguïté.
*   **Pour le système,** c'est un "commit" transactionnel qui déclenche des changements de statut en base de données, l'attribution de droits fondamentaux (le rôle `Owner`), et qui guide l'utilisateur vers la phase suivante de configuration et de délégation.

La distinction entre les parcours gratuit et payant est essentielle et nécessite une logique conditionnelle dans l'interface et une intégration avancée avec l'API de Stripe pour la gestion des abonnements basés sur l'usage.
