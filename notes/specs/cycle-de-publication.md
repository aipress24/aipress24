# Cycle de Publication AIPress24

## Spécifications Fonctionnelles Détaillées

**Version**: 1.2
**Date**: 2026-01-08
**Statut**: Validé

---

## 1. Vue d'Ensemble

### 1.1 Objectif du Système

AIPress24 est une plateforme de mise en relation entre :
- **Journalistes** (communauté Press & Media)
- **Experts** (communauté Leaders & Experts)
- **Communicants** (communauté Communicants)

Le cycle de publication permet aux journalistes de :
1. Proposer des sujets d'articles
2. Recevoir ou émettre des commandes d'articles
3. Solliciter des experts via des avis d'enquête
4. Produire et publier des articles
5. Notifier les participants de la publication

### 1.2 Cycle Simplifié

```
┌─────────┐     ┌───────────┐     ┌──────────────┐     ┌─────────┐     ┌────────────────────────┐
│  SUJET  │ ──▶ │ COMMANDE  │ ──▶ │ AVIS ENQUÊTE │ ──▶ │ ARTICLE │ ──▶ │ NOTIF. DE PUBLICATION  │
└─────────┘     └───────────┘     └──────────────┘     └─────────┘     └────────────────────────┘
   (1)              (2)                (3)                (4)                   (5)
```

**Note importante** : Ce cycle n'est pas strictement linéaire. Un article peut être créé directement sans passer par les étapes Sujet, Commande ou Avis d'Enquête.

---

## 2. Acteurs et Rôles

### 2.1 Rôles Système

| Rôle Technique | Nom Français | Communauté | Description |
|----------------|--------------|------------|-------------|
| `PRESS_MEDIA` | Journaliste | Press & Media | Crée sujets, commandes, articles |
| `EXPERT` | Expert | Leaders & Experts | Répond aux avis d'enquête, fournit expertise |
| `PRESS_RELATIONS` | Communicant | Communicants | Relations presse, communiqués |
| `ACADEMIC` | Académique | Academics | Recherche, publications académiques |
| `TRANSFORMER` | Transformeur | Transformers | Innovation, transformation |
| `LEADER` | Responsable | - | Responsable d'organisation |
| `MANAGER` | Gestionnaire | - | Gestionnaire d'organisation |
| `ADMIN` | Administrateur | - | Administration système |

JD: En plus des Leaders & Experts, tous les acteurs peuvent répondre à un avis d'enquête.

### 2.2 Rôles Métier dans le Cycle

| Rôle Métier | Description | Actions Principales |
|-------------|-------------|---------------------|
| **Auteur** (`owner`) | Créateur du contenu | Crée, modifie, soumet, valide, publie |
| **Commanditaire** (`commanditaire`) | Celui qui commande l'article | Initie la demande (pas de validation requise) |
| **Média** (`media`) | Organisation média | Contexte de publication |
| **Éditeur** (`publisher`) | Organisation qui publie | Publie officiellement |

### 2.3 Matrice des Permissions

Les permissions sont gérées **au niveau des rôles** (pas individuellement).

| Action | Journaliste | Expert | Commanditaire | Admin |
|--------|-------------|--------|---------------|-------|
| Créer Sujet | ✓ | ✗ | ✗ | ✓ |
| Créer Commande | ✓ | ✗ | ✓ | ✓ |
| Créer Avis d'Enquête | ✓ | ✗ | ✗ | ✓ |
| Répondre Avis d'Enquête | ✓ | ✓ | ✓ | ✓ |
| Créer Article | ✓ | ✗ | ✗ | ✓ |
| Valider/Publier Article | ✓ | ✗ | ✗ | ✓ |
| Envoyer Notification Publication | ✓ | ✗ | ✗ | ✓ |

### 2.4 Visibilité des Avis d'Enquête

Un expert ne peut voir que les avis d'enquête **qui le concernent directement** (ceux pour lesquels il a été ciblé). Il n'a pas accès à l'ensemble des avis d'enquête du système.

---

## 3. Entités du Cycle

### 3.1 Sujet (`nrm_sujet`)

#### Description
Un **Sujet** est une proposition de thème d'article. Il peut être proposé par un journaliste à sa rédaction, ou par un commanditaire externe.

#### Champs Principaux

| Champ | Type | Description | Obligatoire |
|-------|------|-------------|-------------|
| `titre` | String | Titre du sujet | Oui |
| `brief` | Text | Résumé/accroche | Non |
| `contenu` | Text | Description détaillée | Non |
| `owner_id` | FK User | Auteur du sujet | Oui |
| `commanditaire_id` | FK User | Commanditaire (si externe) | Non |
| `media_id` | FK Organisation | Média concerné | Non |
| `date_limite_validite` | DateTime | Date limite de validité (indicative) | Non |
| `date_parution_prevue` | DateTime | Date de parution visée | Non |
| `status` | String | État du sujet | Oui |

**Note** : Le champ `date_limite_validite` est purement indicatif à ce stade. Le système ne gère pas l'expiration automatique.

#### Métadonnées (héritées de `NewsMetadataMixin`)

| Champ | Type | Description |
|-------|------|-------------|
| `genre` | String | Genre journalistique |
| `section` | String | Section/rubrique |
| `topic` | String | Thématique |
| `sector` | List[String] | Secteurs d'activité |
| `geo_localisation` | String | Localisation géographique |
| `language` | String | Langue |

#### Ciblage (hérité de `CiblageMixin`)

| Champ | Type | Description |
|-------|------|-------------|
| `ciblage_secteur_detailles` | List[String] | Secteurs ciblés |
| `ciblage_directions_expertise` | List[String] | Domaines d'expertise visés |
| `ciblage_fonction` | List[String] | Fonctions visées |
| `ciblage_type_organisation` | List[String] | Types d'organisations |
| `ciblage_taille_organisation` | List[String] | Tailles d'organisations |
| `ciblage_geo` | List[String] | Zones géographiques |

#### États du Sujet

```
┌─────────────┐
│  BROUILLON  │ ◀──────────────────────────┐
└──────┬──────┘                            │
       │ soumettre                         │ refuser/annuler
       ▼                                   │
┌─────────────┐     ┌─────────────┐        │
│ EN_DISCUSSION│ ──▶│   ACCEPTÉ   │────────┤
└──────┬──────┘     └──────┬──────┘        │
       │                   │ valider       │
       │                   ▼               │
       │            ┌─────────────┐        │
       │            │   VALIDÉ    │        │
       │            └──────┬──────┘        │
       │                   │ publier       │
       │                   ▼               │
       │            ┌─────────────┐        │
       └───────────▶│   PUBLIÉ    │        │
                    └─────────────┘        │
                                           │
┌─────────────┐                            │
│   REFUSÉ    │ ◀──────────────────────────┤
└─────────────┘                            │
                                           │
┌─────────────┐                            │
│   ANNULÉ    │ ◀──────────────────────────┘
└─────────────┘
```

**Note** : La machine à états n'est pas strictement implémentée dans le code actuel. Le champ `status` est un simple String. L'utilisation d'Enums serait préférable pour améliorer la robustesse.

---

### 3.2 Commande (`nrm_commande`)

#### Description
Une **Commande** formalise la demande d'écriture d'un article. Elle peut découler d'un Sujet accepté ou être créée directement.

#### Champs Spécifiques

| Champ | Type | Description | Obligatoire |
|-------|------|-------------|-------------|
| `date_limite_validite` | DateTime | Validité de la commande (indicative) | Non |
| `date_bouclage` | DateTime | Date de bouclage (deadline) | Non |
| `date_parution_prevue` | DateTime | Date de parution prévue | Non |
| `date_paiement` | DateTime | Date de paiement (non géré) | Non |
| `status` | String | État de la commande | Oui |

**Note** : Le paiement n'est pas géré dans le système. Le champ `date_paiement` est purement informatif.

#### États de la Commande

Identiques au Sujet :
- `BROUILLON` → `EN_DISCUSSION` → `ACCEPTÉ` → `VALIDÉ` → `PUBLIÉ`
- Ou : `REFUSÉ`, `ANNULÉ`

#### Relation avec le Sujet

Le code actuel ne définit pas de relation FK explicite entre Commande et Sujet. Une Commande peut être créée indépendamment d'un Sujet.

---

### 3.3 Avis d'Enquête (`nrm_avis_enquete`)

#### Description
Un **Avis d'Enquête** permet à un journaliste de solliciter des experts pour obtenir des informations, témoignages ou avis dans le cadre d'un article.

#### Types d'Avis

| Code | Nom | Description |
|------|-----|-------------|
| `AVIS_D_ENQUETE` | Avis d'enquête | Demande d'information générale |
| `APPEL_A_TEMOIN` | Appel à témoin | Recherche de témoignages |
| `APPEL_A_EXPERT` | Appel à expert | Sollicitation d'expertise |

#### Champs Spécifiques

| Champ | Type | Description |
|-------|------|-------------|
| `type_avis` | Enum TypeAvis | Type de l'avis |
| `date_debut_enquete` | DateTime (TZ) | Début de l'enquête |
| `date_fin_enquete` | DateTime (TZ) | Fin de l'enquête |
| `date_bouclage` | DateTime | Date de bouclage |
| `date_parution_prevue` | DateTime | Parution prévue |
| `status` | String | État de l'avis |

#### États de l'Avis d'Enquête

```
┌─────────────┐
│  BROUILLON  │
└──────┬──────┘
       │ valider
       ▼
┌─────────────┐
│   VALIDÉ    │  ──▶ Envoi aux experts ciblés
└──────┬──────┘
       │ (après réception réponses)
       ▼
┌─────────────┐
│   PUBLIÉ    │  ──▶ Clôture de l'avis
└─────────────┘
```

---

### 3.4 Contact Avis d'Enquête (`nrm_contact_avis_enquete`)

#### Description
Représente la relation entre un Avis d'Enquête et un Expert contacté. Gère le workflow de réponse et de prise de rendez-vous.

#### Champs Principaux

| Champ | Type | Description |
|-------|------|-------------|
| `avis_enquete_id` | FK AvisEnquete | L'avis concerné |
| `journaliste_id` | FK User | Le journaliste initiateur |
| `expert_id` | FK User | L'expert contacté |
| `status` | Enum StatutAvis | Réponse de l'expert |
| `date_reponse` | DateTime | Date de réponse |

#### Statuts de Réponse Expert

| Code | Nom | Description |
|------|-----|-------------|
| `EN_ATTENTE` | En attente | L'expert n'a pas encore répondu |
| `ACCEPTE` | Accepté | L'expert accepte de participer |
| `REFUSE` | Refusé | L'expert décline |
| `REFUSE_SUGGESTION` | Refusé avec suggestion | L'expert décline mais suggère un autre contact |

#### Machine à États - Réponse Expert

```
                    ┌─────────────┐
                    │  EN_ATTENTE │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
    │   ACCEPTÉ   │ │   REFUSÉ    │ │ REFUSÉ_SUGGESTION│
    └──────┬──────┘ └─────────────┘ └──────────────────┘
           │
           │ Si accepté, workflow RDV disponible
           ▼
    ┌─────────────────────────────────────┐
    │     WORKFLOW RENDEZ-VOUS (RDV)      │
    └─────────────────────────────────────┘
```

---

### 3.5 Workflow Rendez-Vous (RDV)

#### Description
Quand un expert accepte un avis d'enquête, un workflow de prise de rendez-vous se déclenche.

#### Types de Rendez-Vous

| Code | Nom | Champ requis |
|------|-----|--------------|
| `PHONE` | Téléphone | `rdv_phone` |
| `VIDEO` | Visioconférence | `rdv_video_link` |
| `F2F` | Face à face | `rdv_address` |

#### Champs RDV

| Champ | Type | Description |
|-------|------|-------------|
| `rdv_type` | Enum RDVType | Type de RDV |
| `rdv_status` | Enum RDVStatus | État du RDV |
| `proposed_slots` | JSON List | Créneaux proposés (ISO datetime) |
| `date_rdv` | DateTime | Créneau final retenu |
| `rdv_phone` | String | N° téléphone (si PHONE) |
| `rdv_video_link` | String | Lien visio (si VIDEO) |
| `rdv_address` | String | Adresse (si F2F) |
| `rdv_notes_journaliste` | Text | Notes du journaliste |
| `rdv_notes_expert` | Text | Notes de l'expert |

#### Machine à États - RDV

```
┌─────────────┐
│   NO_RDV    │  (État initial après ACCEPTÉ)
└──────┬──────┘
       │ propose_rdv()
       │ - Journaliste propose 1-5 créneaux
       │ - Spécifie type + coordonnées
       ▼
┌─────────────┐
│  PROPOSED   │  (En attente de choix expert)
└──────┬──────┘
       │ accept_rdv()
       │ - Expert choisit un créneau
       │ - Peut ajouter des notes
       ▼
┌─────────────┐
│  ACCEPTED   │  (Créneau choisi)
└──────┬──────┘
       │ confirm_rdv() [optionnel]
       ▼
┌─────────────┐
│  CONFIRMED  │  (RDV confirmé)
└─────────────┘

À tout moment : cancel_rdv() ──▶ retour à NO_RDV
```

#### Règles de Validation des Créneaux

| Règle | Description |
|-------|-------------|
| Nombre | 1 à 5 créneaux maximum |
| Futur | Tous les créneaux doivent être dans le futur |
| Heures ouvrées | Entre 9h00 et 18h00 |
| Jours ouvrés | Du lundi au vendredi (pas de week-end) |
| Fuseau horaire | UTC par défaut, ou timezone-aware |

---

### 3.6 Article (`nrm_article`)

#### Description
L'**Article** est le contenu final produit par le journaliste, potentiellement enrichi par les contributions des experts.

**Règle importante** : Un article peut être créé directement, sans être lié à une Commande ou un Sujet préalable.

#### Champs Spécifiques

| Champ | Type | Description |
|-------|------|-------------|
| `chapo` | Text | Chapeau (paragraphe d'accroche) |
| `copyright` | String | Informations de copyright |
| `date_parution_prevue` | DateTime (TZ) | Date de parution prévue |
| `date_publication_aip24` | DateTime | Date de publication sur AIP24 |
| `published_at` | DateTime (TZ) | Horodatage de publication |
| `expired_at` | DateTime (TZ) | Date d'expiration |
| `status` | Enum PublicationStatus | État de publication |
| `publisher_id` | FK Organisation | Organisation éditrice |

#### Galerie d'Images (`nrm_image`)

| Champ | Type | Description |
|-------|------|-------------|
| `article_id` | FK Article | Article parent |
| `content` | FileObject | Fichier image (S3) |
| `caption` | String | Légende |
| `copyright` | String | Copyright |
| `position` | Integer | Ordre dans le carousel |

#### États de l'Article

```
┌─────────────┐
│    DRAFT    │  (Brouillon)
└──────┬──────┘
       │ publish()
       │ - Vérifie titre non vide
       │ - Vérifie contenu non vide
       │ - Définit published_at
       ▼
┌─────────────┐
│   PUBLIC    │  (Publié)
└──────┬──────┘
       │ unpublish()
       ▼
┌─────────────┐
│    DRAFT    │  (Retour brouillon)
└─────────────┘

Note: expired_at peut rendre l'article invisible
même s'il est PUBLIC (is_expired property)
```

#### Workflow de Validation

Le **journaliste** est responsable de toutes les transitions d'état :
- Brouillon → Validé → Publié
- Pas de validation par un rédacteur en chef requise

#### Expiration des Articles

Quand `expired_at` est atteint :
- L'article reste conservé côté back-office
- Le front-office (autre module) gère l'affichage/masquage
- Pas de suppression ou d'archivage automatique dans ce module

#### Méthodes Métier

```python
# Vérifications
article.can_publish()    # True si status == DRAFT
article.can_unpublish()  # True si status == PUBLIC
article.is_draft         # Property
article.is_public        # Property
article.is_expired       # True si expired_at < maintenant

# Actions
article.publish(publisher_id=None)  # DRAFT → PUBLIC
article.unpublish()                 # PUBLIC → DRAFT
```

---

### 3.7 Notification de Publication (`nrm_notification_publication`)

#### Description
La **Notification de Publication** est une fonctionnalité de communication dans WIP. Elle permet au journaliste de notifier les personnes ayant participé à son enquête que l'article a été publié.

> **Distinction importante** : Ne pas confondre avec le "Justificatif de Publication" qui est un **produit commercial** vendu sur la Marketplace (module BIZ). Le justificatif commercial permet aux entreprises citées d'acheter le droit de republier l'article (PDF non modifiable) sur leur site web.

#### Workflow

1. Le journaliste publie son article
2. Il va dans "Notifications de publication"
3. Il voit la liste de ses enquêtes (Avis d'Enquête)
4. Il sélectionne l'enquête concernée
5. S'affiche la liste des personnes ayant participé (issue des contacts de l'Avis d'Enquête)
6. Il retire les personnes non mentionnées dans l'article final
7. Il sélectionne l'article publié parmi ses articles
8. Il clique sur "Notifier la publication"
9. Les destinataires reçoivent :
   - Une notification in-app dans WORK/OPPORTUNITÉS/Justificatifs
   - Un email avec le message type (voir ci-dessous)

#### Champs Spécifiques

| Champ | Type | Description |
|-------|------|-------------|
| `avis_enquete_id` | FK AvisEnquete | L'avis d'enquête concerné |
| `article_id` | FK Article | L'article publié |
| `notified_at` | DateTime | Date d'envoi des notifications |

#### Contacts Notifiés (`nrm_notification_publication_contact`)

| Champ | Type | Description |
|-------|------|-------------|
| `notification_id` | FK NotificationPublication | La notification parente |
| `contact_id` | FK ContactAvisEnquete | Le contact notifié |
| `email_sent` | Boolean | Email envoyé |
| `email_sent_at` | DateTime | Date d'envoi email |

#### Message Email Type

```
Bonjour [Prénom, Nom de la personne],

Nous avons le plaisir de vous informer que vous êtes mentionné(e)
dans un article publié sur AiPRESS24.

Si vous souhaitez que cet article renforce votre notoriété, nous vous
invitons à vous connecter à AiPRESS24 et à vous rendre dans votre espace
personnel WORK, cliquez sur Opportunités en colonne de gauche, puis sur
Justificatifs.

Vous pourrez alors en acheter le droit de diffusion sur votre profil
personnel ainsi que sur celui de votre organisation.

A bientôt sur AiPRESS24 pour créer et partager la valeur de l'information.

Cordialement
```

#### Comportement

- **Lien Avis d'Enquête → Article** : La notification établit le lien entre l'enquête et l'article final
- **Sélection des destinataires** : Le journaliste peut exclure des contacts qui ne sont pas mentionnés
- **Notification in-app + email** : Deux canaux simultanés
- **Invitation commerciale** : Le message invite à acheter le justificatif commercial (module BIZ)

---

### 3.8 Justificatif Commercial (Module BIZ - Hors Scope)

> **Note** : Cette section décrit un produit du module BIZ (Marketplace), pas du module WIP.

Le **Justificatif de Publication Commercial** est un produit vendu sur la place de marché :

| Aspect | Description |
|--------|-------------|
| **Destinataires** | Entreprises et organisations citées dans un article |
| **Usage** | Droit d'afficher légalement l'article sur leur site web |
| **Format** | PDF non modifiable |
| **Achat** | Via WORK/OPPORTUNITÉS/Justificatifs après notification |

Ce produit n'est pas géré dans le module WIP.

---

## 4. Flux de Travail Complets

### 4.1 Scénario 1 : Cycle Complet Standard

```
JOURNALISTE                    SYSTÈME                      EXPERT
    │                            │                            │
    │  1. Crée Sujet             │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  2. Sujet validé           │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  3. Crée Commande          │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  4. Crée Avis d'Enquête    │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  5. Cible des experts      │  6. Notification           │
    │ ─────────────────────────▶ │ ─────────────────────────▶ │
    │                            │                            │
    │                            │  7. Expert répond ACCEPTÉ  │
    │                            │ ◀───────────────────────── │
    │                            │                            │
    │  8. Propose créneaux RDV   │  9. Notification           │
    │ ─────────────────────────▶ │ ─────────────────────────▶ │
    │                            │                            │
    │                            │  10. Expert choisit        │
    │  11. Notification          │ ◀───────────────────────── │
    │ ◀───────────────────────── │                            │
    │                            │                            │
    │  12. RDV a lieu            │                            │
    │ ◀─ ─ ─ ─ ─ ─ ─ ─ ── ─ ─ ─ ─│─ ─ ─ ── ─ ─ ─ ─ ─ ─ ─ ─ ─ ▶│
    │                            │                            │
    │  13. Rédige Article        │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  14. Publie Article        │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  15. Notifie publication   │  16. Notification + Email  │
    │ ─────────────────────────▶ │ ─────────────────────────▶ │
    │                            │                            │
```

### 4.2 Scénario 2 : Article Direct (sans Sujet/Commande)

```
JOURNALISTE                    SYSTÈME
    │                            │
    │  1. Crée Article           │
    │ ─────────────────────────▶ │
    │                            │
    │  2. Rédige contenu         │
    │ ─────────────────────────▶ │
    │                            │
    │  3. Publie Article         │
    │ ─────────────────────────▶ │
    │                            │
```

### 4.3 Scénario 3 : Expert Refuse

```
JOURNALISTE                    SYSTÈME                      EXPERT
    │                            │                            │
    │  Crée Avis d'Enquête       │                            │
    │ ─────────────────────────▶ │                            │
    │                            │                            │
    │  Cible Expert A            │  Notification              │
    │ ─────────────────────────▶ │ ─────────────────────────▶ │
    │                            │                            │
    │                            │  Expert A refuse           │
    │  Notification              │ ◀───────────────────────── │
    │ ◀───────────────────────── │                            │
    │                            │                            │
    │  Cible Expert B            │  Notification              │
    │ ─────────────────────────▶ │ ─────────────────────────▶ │
    │                            │                            │
    │                            │  Expert B accepte          │
    │ ◀───────────────────────── │ ◀───────────────────────── │
    │                            │                            │
    │  (suite workflow RDV...)   │                            │
```

---

## 5. Règles Métier

### 5.1 Règles de Publication d'Article

| Règle | Description |
|-------|-------------|
| Titre obligatoire | `titre` ne peut pas être vide |
| Contenu obligatoire | `contenu` ne peut pas être vide |
| État DRAFT requis | Seul un article DRAFT peut être publié |
| Horodatage automatique | `published_at` défini automatiquement lors de la publication |
| Validation par journaliste | Le journaliste valide lui-même ses articles |

### 5.2 Règles de Proposition RDV

| Règle | Description |
|-------|-------------|
| Expert accepté | `status` doit être `ACCEPTE` |
| Pas de RDV existant | `rdv_status` doit être `NO_RDV` |
| 1-5 créneaux | Minimum 1, maximum 5 propositions |
| Créneaux futurs | Tous > datetime.now(UTC) |
| Heures ouvrées | 9h00-18h00 uniquement |
| Jours ouvrés | Lundi-Vendredi uniquement |
| Coordonnées requises | Selon type (phone/video/address) |

### 5.3 Règles d'Acceptation RDV

| Règle | Description |
|-------|-------------|
| État PROPOSED | RDV doit être en état `PROPOSED` |
| Créneau valide | Doit être dans `proposed_slots` |

### 5.4 Règles de Liaison entre Entités

| Relation | Obligatoire | Description |
|----------|-------------|-------------|
| Commande → Sujet | Non | Une commande peut exister sans sujet |
| Article → Commande | Non | Un article peut être créé directement |
| Article → Avis d'Enquête | Non | Un article peut être créé sans avis |
| Justificatif → Article | Oui | Un justificatif est toujours lié à un article |

### 5.5 Règles de Validation Hiérarchique

| Aspect | Règle |
|--------|-------|
| Validation article | Par le journaliste uniquement |
| Validation par rédacteur en chef | Non requise |
| Validation par commanditaire | Non requise |

### 5.6 Règles de Paiement

Le paiement n'est pas géré dans le système. Les champs de date de paiement sont purement informatifs.

---

## 6. Système de Notifications

### 6.1 Principe Général

Une notification est envoyée **à chaque fois qu'une action est attendue** de la part d'une ou plusieurs personnes autres que celle à l'origine de l'action.

### 6.2 Canaux de Notification

Les notifications sont envoyées via **deux canaux** :
- **Email** : Notification externe
- **In-app** : Notification dans l'interface utilisateur

### 6.3 Événements Déclencheurs

| Événement | Destinataire | Description |
|-----------|--------------|-------------|
| Avis d'enquête ciblé | Expert | L'expert est sollicité |
| Expert accepte | Journaliste | L'expert a accepté de participer |
| Expert refuse | Journaliste | L'expert a décliné |
| RDV proposé | Expert | Des créneaux sont proposés |
| RDV accepté | Journaliste | L'expert a choisi un créneau |
| RDV confirmé | Expert | Le journaliste a confirmé |
| RDV annulé | Autre partie | Le RDV est annulé |

---

## 7. Couverture de Tests Recommandée

### 7.1 Tests Unitaires - Modèles

#### Article
```
test_article_creation
test_article_can_publish_when_draft
test_article_cannot_publish_when_public
test_article_publish_requires_title
test_article_publish_requires_content
test_article_publish_sets_published_at
test_article_unpublish_returns_to_draft
test_article_is_expired_when_past_expiry
```

#### ContactAvisEnquete - Réponse
```
test_contact_initial_status_is_en_attente
test_contact_can_accept
test_contact_can_refuse
test_contact_can_refuse_with_suggestion
```

#### ContactAvisEnquete - RDV
```
test_propose_rdv_success
test_propose_rdv_fails_if_not_accepted
test_propose_rdv_fails_if_rdv_exists
test_propose_rdv_fails_with_no_slots
test_propose_rdv_fails_with_too_many_slots
test_propose_rdv_fails_with_past_slot
test_propose_rdv_fails_outside_business_hours
test_propose_rdv_fails_on_weekend
test_propose_rdv_requires_phone_for_phone_type
test_propose_rdv_requires_video_link_for_video_type
test_propose_rdv_requires_address_for_f2f_type
test_accept_rdv_success
test_accept_rdv_fails_if_not_proposed
test_accept_rdv_fails_with_invalid_slot
test_cancel_rdv_success
test_cancel_rdv_fails_if_no_rdv
test_confirm_rdv_success
test_confirm_rdv_fails_if_not_accepted
```

#### NotificationPublication
```
test_notification_requires_avis_enquete
test_notification_requires_published_article
test_notification_lists_contacts_from_avis
test_notification_can_exclude_contacts
test_notification_sends_email_to_contacts
test_notification_creates_inapp_notification
test_notification_sets_notified_at
```

### 7.2 Tests Unitaires - Services

#### AvisEnqueteService
```
test_service_propose_rdv_orchestration
test_service_accept_rdv_orchestration
test_service_cancel_rdv_orchestration
test_service_store_contacts
test_service_filter_known_experts
test_service_notify_experts
test_service_send_emails
test_service_get_contacts_for_avis
test_service_get_contacts_with_rdv
```

#### ExpertFilterService
```
test_filter_by_secteur
test_filter_by_metier
test_filter_by_fonction
test_filter_by_type_organisation
test_filter_by_taille_organisation
test_filter_by_pays
test_filter_by_departement
test_filter_by_ville
test_filter_multiple_criteria
test_filter_state_persistence
```

### 7.3 Tests d'Intégration

```
test_full_publication_cycle
test_avis_enquete_to_article_flow
test_expert_invitation_and_rdv_flow
test_article_publication_with_images
test_multiple_experts_same_avis
test_expert_refuses_then_another_accepts
test_direct_article_creation_without_commande
test_notification_after_publication
test_notification_email_sent_to_all_contacts
```

### 7.4 Tests E2E

```
test_journalist_creates_full_cycle_via_ui
test_expert_responds_to_avis_via_ui
test_rdv_scheduling_via_ui
test_article_publication_via_ui
test_expert_can_only_see_own_avis
```

---

## 8. Annexes

### 8.1 Fichiers Source Principaux

| Fichier | Contenu |
|---------|---------|
| `src/app/modules/wip/models/newsroom/sujet.py` | Modèle Sujet |
| `src/app/modules/wip/models/newsroom/commande.py` | Modèle Commande |
| `src/app/modules/wip/models/newsroom/avis_enquete.py` | Modèles AvisEnquete, ContactAvisEnquete |
| `src/app/modules/wip/models/newsroom/article.py` | Modèles Article, Image |
| `src/app/modules/wip/models/newsroom/notification_publication.py` | Modèle NotificationPublication |
| `src/app/modules/wip/services/newsroom/avis_enquete_service.py` | Service orchestration |
| `src/app/modules/wip/services/newsroom/expert_filter.py` | Service filtrage experts |
| `src/app/models/auth.py` | Modèles User, Role |
| `src/app/enums.py` | Enums RoleEnum, CommunityEnum |

### 8.2 Tables Base de Données

| Table | Modèle |
|-------|--------|
| `nrm_sujet` | Sujet |
| `nrm_commande` | Commande |
| `nrm_avis_enquete` | AvisEnquete |
| `nrm_contact_avis_enquete` | ContactAvisEnquete |
| `nrm_article` | Article |
| `nrm_image` | Image |
| `nrm_notification_publication` | NotificationPublication |
| `nrm_notification_publication_contact` | NotificationPublicationContact |
| `aut_user` | User |
| `aut_role` | Role |
| `aut_roles_users` | Association User-Role |

### 8.3 Énumérations

```python
# Types d'Avis d'Enquête
class TypeAvis(Enum):
    AVIS_D_ENQUETE = "avis_d_enquete"
    APPEL_A_TEMOIN = "appel_a_temoin"
    APPEL_A_EXPERT = "appel_a_expert"

# Statut réponse expert
class StatutAvis(Enum):
    EN_ATTENTE = "en_attente"
    ACCEPTE = "accepte"
    REFUSE = "refuse"
    REFUSE_SUGGESTION = "refuse_suggestion"

# Type de RDV
class RDVType(Enum):
    PHONE = "phone"
    VIDEO = "video"
    F2F = "f2f"

# Statut RDV
class RDVStatus(Enum):
    NO_RDV = "no_rdv"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    CONFIRMED = "confirmed"

# Statut publication article
class PublicationStatus(Enum):
    DRAFT = "draft"
    PUBLIC = "public"
```

---

## 9. Historique du Document

| Version | Date | Auteur | Modifications |
|---------|------|--------|---------------|
| 1.0 | 2026-01-08 | SF | Création initiale |
| 1.1 | 2026-01-08 | SF | Intégration des réponses client |
| 1.2 | 2026-01-08 | SF | Distinction Notification (WIP) vs Justificatif commercial (BIZ) |

---

## 10. Prochaines Étapes

1. **Renommer/Créer le modèle NotificationPublication** : Remplacer JustifPublication par le nouveau modèle
2. **Implémenter le workflow de notification** : Sélection enquête → contacts → article → envoi
3. **Intégrer les notifications in-app** : Créer les entrées dans WORK/OPPORTUNITÉS/Justificatifs
4. **Implémenter l'envoi d'emails** : Template d'email de notification
5. **Compléter les tests** : Implémenter les tests listés en section 7
6. **Améliorer les Enums Sujet/Commande** : Remplacer les String status par des Enums stricts
7. **Documenter les API** : Créer une doc API REST si nécessaire

> **Note** : Le Justificatif Commercial (PDF achetable) sera implémenté dans le module BIZ, pas WIP.
