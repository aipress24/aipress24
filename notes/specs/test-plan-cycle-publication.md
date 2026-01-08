# Plan de Tests - Cycle de Publication

## Objectif

Implémenter la couverture de tests définie dans `notes/specs/cycle-de-publication.md` section 7.

---

## 1. Analyse de l'Existant

### Tests Existants

| Fichier | Lignes | Couverture |
|---------|--------|------------|
| `tests/a_unit/modules/wip/newsroom/test_avis_enquete.py` | 687 | Complète pour RDV |
| `tests/a_unit/modules/wip/newsroom/test_article.py` | 186 | Bonne |
| `tests/a_unit/modules/wip/services/test_avis_enquete_service.py` | 456 | Bonne |
| `tests/c_e2e/modules/wip/newsroom/test_articles_views.py` | ~50 | Basique |

### Lacunes Identifiées

| Composant | Status | Priorité |
|-----------|--------|----------|
| ExpertFilterService | **Aucun test** | Haute |
| NotificationPublication | **Aucun test** | Haute |
| ContactAvisEnquete - Réponse | Partiel | Moyenne |
| Tests d'intégration workflow | Manquants | Haute |
| Tests E2E spécifiques | Partiels | Moyenne |

---

## 2. Structure des Fichiers de Test

```
tests/
├── a_unit/
│   └── modules/
│       └── wip/
│           ├── newsroom/
│           │   ├── test_avis_enquete.py        ✓ Existe
│           │   ├── test_article.py             ✓ Existe
│           │   ├── test_contact_response.py    ← NOUVEAU
│           │   └── test_notification_publication.py  ← NOUVEAU
│           └── services/
│               ├── test_avis_enquete_service.py  ✓ Existe
│               └── test_expert_filter_service.py ← NOUVEAU
├── b_integration/
│   └── modules/
│       └── wip/
│           └── test_publication_cycle.py       ← NOUVEAU
└── c_e2e/
    └── modules/
        └── wip/
            └── newsroom/
                ├── test_articles_views.py      ✓ Existe
                ├── test_avis_enquete_views.py  ← NOUVEAU
                └── test_rdv_workflow_e2e.py    ← NOUVEAU
```

---

## 3. Phase 1 : Tests Unitaires Manquants (Priorité Haute)

### 3.1 ExpertFilterService (`test_expert_filter_service.py`)

**Durée estimée** : 2-3h

**Prérequis** : Créer des fixtures avec des profils utilisateurs variés

```python
# tests/a_unit/modules/wip/services/test_expert_filter_service.py

class TestSectorSelector:
    """Tests pour le filtrage par secteur d'activité."""

    def test_filter_by_secteur_single():
        """Filtre avec un seul secteur sélectionné."""

    def test_filter_by_secteur_multiple():
        """Filtre avec plusieurs secteurs (OR logic intra-critère)."""

    def test_filter_by_secteur_no_match():
        """Aucun expert ne correspond au secteur."""


class TestMetierSelector:
    """Tests pour le filtrage par métier."""

    def test_filter_by_metier_primary():
        """Filtre sur métier principal."""

    def test_filter_by_metier_secondary():
        """Filtre inclut métiers secondaires (User.tous_metiers)."""


class TestFonctionSelector:
    """Tests pour le filtrage par fonction."""

    def test_filter_by_fonction():
        """Filtre par fonction."""


class TestOrganisationSelectors:
    """Tests pour type et taille d'organisation."""

    def test_filter_by_type_organisation():
        """Filtre par type d'organisation."""

    def test_filter_by_taille_organisation():
        """Filtre par taille d'organisation."""

    def test_taille_label_conversion():
        """Vérifie la conversion code → label."""


class TestGeoSelectors:
    """Tests pour pays, département, ville."""

    def test_filter_by_pays():
        """Filtre par pays."""

    def test_filter_by_departement():
        """Filtre par département (dépend de pays)."""

    def test_filter_by_ville():
        """Filtre par ville (dépend de département)."""

    def test_departement_requires_pays():
        """Département non disponible sans sélection pays."""

    def test_ville_requires_departement():
        """Ville non disponible sans sélection département."""


class TestMultipleCriteria:
    """Tests pour combinaison de critères."""

    def test_filter_multiple_criteria_and_logic():
        """Critères multiples appliquent AND entre catégories."""

    def test_filter_empty_returns_all():
        """Aucun critère retourne tous les experts (limité)."""


class TestStateManagement:
    """Tests pour la gestion d'état en session."""

    def test_state_persistence():
        """L'état est sauvegardé en session."""

    def test_state_restoration():
        """L'état est restauré depuis la session."""

    def test_clear_state():
        """L'état peut être effacé."""

    def test_update_state_from_htmx_request():
        """Mise à jour depuis requête HTMX."""


class TestExpertSelection:
    """Tests pour la sélection d'experts."""

    def test_add_experts_from_request():
        """Ajout d'experts depuis formulaire."""

    def test_update_experts_from_request():
        """Remplacement de la sélection."""

    def test_get_selected_experts():
        """Récupération des experts sélectionnés."""

    def test_max_selectable_experts():
        """Limite de MAX_SELECTABLE_EXPERTS (50)."""
```

### 3.2 ContactAvisEnquete Réponse (`test_contact_response.py`)

**Durée estimée** : 1h

```python
# tests/a_unit/modules/wip/newsroom/test_contact_response.py

class TestContactInitialState:
    """Tests pour l'état initial du contact."""

    def test_initial_status_is_en_attente():
        """Le statut initial est EN_ATTENTE."""

    def test_initial_date_reponse_is_none():
        """La date de réponse est None initialement."""


class TestContactAccept:
    """Tests pour l'acceptation."""

    def test_accept_changes_status():
        """accept() change le statut en ACCEPTE."""

    def test_accept_sets_date_reponse():
        """accept() définit la date de réponse."""

    def test_accept_enables_rdv_proposal():
        """Après accept(), can_propose_rdv() retourne True."""


class TestContactRefuse:
    """Tests pour le refus."""

    def test_refuse_changes_status():
        """refuse() change le statut en REFUSE."""

    def test_refuse_sets_date_reponse():
        """refuse() définit la date de réponse."""


class TestContactRefuseWithSuggestion:
    """Tests pour le refus avec suggestion."""

    def test_refuse_with_suggestion_changes_status():
        """Le statut devient REFUSE_SUGGESTION."""

    def test_refuse_with_suggestion_stores_suggestion():
        """La suggestion est stockée."""
```

### 3.3 NotificationPublication (`test_notification_publication.py`)

**Durée estimée** : 1h

**Note** : La NotificationPublication est une fonctionnalité de communication dans WIP (pas un produit commercial).
Elle permet au journaliste de notifier les participants d'une enquête que l'article a été publié.

> **Distinction importante** : Le "Justificatif de Publication" (PDF commercial) est un produit du module BIZ, pas WIP.

**Modèle simplifié** :
- Pas de lifecycle (created_at, modified_at, deleted_at)
- Créée au moment de l'envoi
- Envoi email/in-app en fire-and-forget (pas de tracking)

```python
# tests/a_unit/modules/wip/newsroom/test_notification_publication.py

class TestNotificationCreation:
    """Tests pour la création de notification."""

    def test_notification_requires_avis_enquete():
        """Une notification doit être liée à un avis d'enquête."""

    def test_notification_requires_article():
        """Une notification doit être liée à un article."""

    def test_notification_sets_notified_at_on_creation():
        """La date de notification est définie automatiquement à la création."""

    def test_notification_has_owner():
        """La notification est liée au journaliste (owner)."""


class TestNotificationContacts:
    """Tests pour les contacts notifiés."""

    def test_notification_can_have_multiple_contacts():
        """Une notification peut avoir plusieurs contacts."""

    def test_contact_links_to_contact_avis_enquete():
        """Chaque contact est lié à un ContactAvisEnquete."""
```

---

## 4. Phase 2 : Tests d'Intégration (Priorité Haute)

### 4.1 Publication Cycle (`test_publication_cycle.py`)

**Durée estimée** : 4h

**Prérequis** : Fixtures réutilisables pour Sujet, Commande, AvisEnquete, Article

```python
# tests/b_integration/modules/wip/test_publication_cycle.py

class TestFullPublicationCycle:
    """Test du cycle complet de publication."""

    def test_full_cycle_sujet_to_notification():
        """
        Cycle complet :
        1. Journaliste crée Sujet
        2. Sujet validé
        3. Création Commande
        4. Création AvisEnquete
        5. Ciblage experts
        6. Expert accepte
        7. RDV proposé et accepté
        8. Article créé et publié
        9. Notification de publication envoyée
        """


class TestAvisEnqueteToArticleFlow:
    """Flux Avis d'Enquête → Article."""

    def test_multiple_experts_contribute():
        """Plusieurs experts répondent au même avis."""

    def test_article_created_after_rdv():
        """Article créé après RDV terminé."""


class TestExpertInvitationFlow:
    """Flux d'invitation expert et RDV."""

    def test_invitation_sends_notification():
        """L'invitation déclenche une notification."""

    def test_invitation_sends_email():
        """L'invitation envoie un email."""

    def test_rdv_acceptance_notifies_journalist():
        """L'acceptation du RDV notifie le journaliste."""


class TestDirectArticleCreation:
    """Création directe d'article (sans cycle)."""

    def test_article_without_sujet():
        """Article créé sans Sujet préalable."""

    def test_article_without_commande():
        """Article créé sans Commande."""

    def test_article_without_avis():
        """Article créé sans Avis d'Enquête."""


class TestExpertRefusalScenario:
    """Scénario de refus d'expert."""

    def test_expert_refuses_then_another_accepts():
        """
        1. Expert A refuse
        2. Journaliste cible Expert B
        3. Expert B accepte
        4. RDV planifié avec Expert B
        """

    def test_all_experts_refuse():
        """Tous les experts refusent."""


class TestNotificationAfterPublication:
    """Notification après publication."""

    def test_notification_sent_after_publication():
        """Notification envoyée après publication article."""

    def test_notification_linked_to_correct_article():
        """Notification liée au bon article."""

    def test_notification_linked_to_correct_avis():
        """Notification liée au bon avis d'enquête."""

    def test_all_contacts_receive_email():
        """Tous les contacts sélectionnés reçoivent un email."""
```

---

## 5. Phase 3 : Tests E2E (Priorité Moyenne)

### 5.1 Avis d'Enquête Views (`test_avis_enquete_views.py`)

**Durée estimée** : 3h

```python
# tests/c_e2e/modules/wip/newsroom/test_avis_enquete_views.py

class TestJournalistAvisEnqueteViews:
    """Tests E2E pour les vues journaliste."""

    def test_create_avis_enquete():
        """Création d'un avis via formulaire."""

    def test_ciblage_experts():
        """Interface de ciblage des experts."""

    def test_view_responses():
        """Affichage des réponses des experts."""

    def test_propose_rdv_form():
        """Formulaire de proposition de RDV."""


class TestExpertAvisEnqueteViews:
    """Tests E2E pour les vues expert."""

    def test_expert_sees_only_own_avis():
        """Expert ne voit que les avis qui le concernent."""

    def test_expert_can_accept():
        """Expert peut accepter l'avis."""

    def test_expert_can_refuse():
        """Expert peut refuser l'avis."""

    def test_expert_can_accept_rdv():
        """Expert peut choisir un créneau RDV."""
```

### 5.2 RDV Workflow E2E (`test_rdv_workflow_e2e.py`)

**Durée estimée** : 2h

```python
# tests/c_e2e/modules/wip/newsroom/test_rdv_workflow_e2e.py

class TestRdvSchedulingE2E:
    """Tests E2E du workflow RDV complet."""

    def test_rdv_full_workflow():
        """
        1. Journaliste propose créneaux
        2. Expert voit notification
        3. Expert choisit créneau
        4. Journaliste voit confirmation
        """

    def test_rdv_cancellation():
        """Annulation de RDV via UI."""

    def test_rdv_details_display():
        """Affichage des détails du RDV."""
```

---

## 6. Ordre d'Implémentation Recommandé

### Sprint 1 (Priorité Haute - 8h)

| # | Test | Fichier | Durée |
|---|------|---------|-------|
| 1 | ExpertFilterService | `test_expert_filter_service.py` | 3h |
| 2 | ContactAvisEnquete Réponse | `test_contact_response.py` | 1h |
| 3 | NotificationPublication (basic) | `test_notification_publication.py` | 2h |
| 4 | Integration - Direct Article | `test_publication_cycle.py` | 2h |

### Sprint 2 (Priorité Moyenne - 7h)

| # | Test | Fichier | Durée |
|---|------|---------|-------|
| 5 | Integration - Expert Flow | `test_publication_cycle.py` | 2h |
| 6 | NotificationPublication (email/inapp) | `test_notification_publication.py` | 2h |
| 7 | E2E - Avis Views | `test_avis_enquete_views.py` | 3h |

### Sprint 3 (Priorité Moyenne - 4h)

| # | Test | Fichier | Durée |
|---|------|---------|-------|
| 8 | E2E - RDV Workflow | `test_rdv_workflow_e2e.py` | 2h |
| 9 | Integration - Full Cycle | `test_publication_cycle.py` | 2h |

---

## 7. Fixtures Partagées à Créer

```python
# tests/conftest.py ou tests/fixtures/newsroom.py

@pytest.fixture
def journalist(db_session):
    """Créer un utilisateur journaliste."""

@pytest.fixture
def expert(db_session):
    """Créer un utilisateur expert avec profil complet."""

@pytest.fixture
def expert_with_profile(db_session, secteur, metier, pays):
    """Expert avec profil filtrable."""

@pytest.fixture
def media_organisation(db_session):
    """Organisation média."""

@pytest.fixture
def avis_enquete(db_session, journalist, media_organisation):
    """Avis d'enquête prêt à l'emploi."""

@pytest.fixture
def contact_accepted(db_session, avis_enquete, expert):
    """Contact avec statut ACCEPTE."""

@pytest.fixture
def published_article(db_session, journalist, media_organisation):
    """Article publié."""

@pytest.fixture
def notification_publication(db_session, avis_enquete, published_article):
    """Notification de publication prête à l'emploi."""
```

---

## 8. Dépendances et Blockers

### Avant de tester NotificationPublication

1. ✅ **Modèle `NotificationPublication`** créé avec :
   - FK `avis_enquete_id` vers AvisEnquete
   - FK `article_id` vers Article
   - `notified_at` (DateTime, défini à la création)
2. ✅ **Modèle `NotificationPublicationContact`** créé avec :
   - FK `notification_id` vers NotificationPublication
   - FK `contact_id` vers ContactAvisEnquete
3. **Service de notification** (envoi email + in-app) - À créer

> **Note** : `JustifPublication` a été supprimé. Le PDF commercial ("Justificatif") sera géré dans le module BIZ.

### Pour les tests E2E

1. **Fixtures utilisateur avec rôles** (PRESS_MEDIA, EXPERT)
2. **Client de test authentifié** par rôle
3. **Setup des notifications** (mock ou in-memory)

---

## 9. Métriques de Succès

| Métrique | Objectif |
|----------|----------|
| Nouveaux tests | +50 tests minimum |
| Couverture modèles Newsroom | >90% |
| Couverture services | >85% |
| Tests E2E critiques | 100% des workflows documentés |
| Temps d'exécution | <60s pour unit tests |

---

## 10. Checklist de Validation

- [ ] Tous les tests de la section 7.1 du spec implémentés
- [ ] Tous les tests de la section 7.2 du spec implémentés
- [ ] Tests d'intégration pour workflows critiques
- [ ] Tests E2E pour parcours utilisateur
- [ ] Fixtures réutilisables documentées
- [ ] CI passe (1960+ tests → 2010+ tests)
- [ ] Pas de régression sur tests existants

---

*Document créé: 2026-01-08*
*Mis à jour: 2026-01-08 - Distinction Notification (WIP) vs Justificatif commercial (BIZ)*
