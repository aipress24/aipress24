# POC - Prototypes et Expérimentations

Ce répertoire contient une application Flask pour prototyper et valider des concepts (POC - Proof of Concept) avant intégration dans l'application principale.

## Structure

```
src/poc/
├── app.py                    # Application Flask principale
├── blueprints/               # Blueprints pour chaque POC
│   ├── __init__.py
│   ├── bw_activation.py      # Business Wall Activation POC (simple)
│   ├── bw_activation_full/   # Business Wall Activation POC (complet) - Package modulaire
│   │   ├── __init__.py       # Blueprint creation and routes import
│   │   ├── config.py         # BW types configuration
│   │   ├── utils.py          # Helper functions
│   │   ├── README.md         # Package documentation
│   │   └── routes/           # Route handlers by workflow stage
│   │       ├── __init__.py   # Imports all route modules
│   │       ├── stage1.py     # Stage 1: Subscription
│   │       ├── stage2.py     # Stage 2: Contacts
│   │       ├── stage3.py     # Stage 3: Activation
│   │       ├── stage4.py     # Stage 4: Internal roles
│   │       ├── stage5.py     # Stage 5: External partners
│   │       ├── stage6.py     # Stage 6: Missions
│   │       ├── stage7.py     # Stage 7: Content
│   │       └── dashboard.py  # Dashboard and reset
│   └── rights_sales.py       # Rights sales settings POC
└── templates/                # Templates Jinja2
    ├── layout.html           # Layout de base
    ├── poc_index.html        # Page d'accueil du POC
    ├── bw_activation.html    # Template BW activation (simple)
    ├── bw_activation_full/   # Templates BW activation (complet)
    └── rights_sales.html     # Template rights sales
```

## Accès

L'application POC est montée dans le serveur principal à l'URL `/poc/`.

### Développement

```bash
# Lancer le serveur principal (le POC sera accessible à /poc/)
make run
```

Puis ouvrir http://localhost:5000/poc/ dans le navigateur.

### Standalone (pour développement isolé)

```bash
cd src/poc
python -c "from app import create_app; create_app().run(debug=True, port=5001)"
```

Puis ouvrir http://localhost:5001 dans le navigateur.

## POCs Disponibles

### Gestion des Droits de Publication

**URL**: `/poc/rights-sales/`

Prototype d'interface de configuration des droits de publication et des licences d'exploitation de contenus éditoriaux.

**Fonctionnalités**:
- 5 options de configuration de licences :
  - Tous les éditeurs abonnés à BW for Media
  - Liste blanche (sélection de médias autorisés)
  - Liste noire (exclusion de certains médias)
  - Aucune diffusion (privé)
  - Tous les médias (y compris institutionnels)
- Recherche et sélection de médias (liste blanche/noire)
- Interface avec Alpine.js pour affichage conditionnel
- Alerte de non-rétroactivité
- Breadcrumb navigation
- Interface responsive avec Tailwind CSS

### Business Wall Activation (Simple)

**URL**: `/poc/bw-activation/`

Prototype simplifié démontrant le workflow d'activation du Business Wall avec deux parcours:

- **Média (gratuit)**: Acceptation des CGV → Activation immédiate → Rôle Owner
- **Relations Presse (payant)**: Nombre de clients → Simulation paiement → Activation → Rôle Owner

**Fonctionnalités**:
- Simulation de l'état utilisateur/organisation via Flask session
- Deux workflows d'activation distincts
- Attribution automatique du rôle Owner après activation
- Calcul du prix en fonction du nombre de clients (RP)
- Interface avec Tailwind CSS
- Bouton de réinitialisation pour tester différents scénarios

### Business Wall Activation (Complet) ✨

**URL**: `/poc/bw-activation-full/`

Prototype complet basé sur des mockups HTML statiques, incluant tous les types de Business Wall avec un workflow d'onboarding complet.

**Workflow complet en 7 étapes**:

### **Étapes 1-3 : Activation du Business Wall**

1. **Confirmation d'abonnement** (`/confirm-subscription`)
   - Le système suggère un type de BW basé sur le profil KYC
   - Affichage des messages d'onboarding détaillés (conditions, tarification, validation)
   - Possibilité de confirmer le type suggéré ou d'en choisir un autre
   - Interface interactive avec Alpine.js

2. **Nomination des responsables** (`/nominate-contacts`)
   - Désignation du Business Wall Owner (dirigeant décisionnaire)
   - Désignation du contact de facturation (Paying Party)
   - Pré-remplissage intelligent avec les données de l'utilisateur connecté
   - Option pour dupliquer les coordonnées (Owner = Payeur)
   - Formulaire avec validation des champs obligatoires

3. **Activation/Tarification**
   - Pour les BW gratuits : Acceptation des CGV (et accord de diffusion pour Media/Micro)
   - Pour les BW payants : Saisie des informations de tarification (nb de clients ou salariés)
   - Simulation de paiement Stripe pour les BW payants
   - Message de confirmation personnalisé selon le type de BW
   - Attribution automatique du rôle "Business Wall Owner"

### **Étapes 4-7 : Gestion du Business Wall**

4. **Gérer les rôles internes** (`/manage-internal-roles`)
   - Inviter des Business Wall Managers Internes (BWMi)
   - Inviter des Press/PR Managers Internes (BWPRi)
   - Workflow d'invitation par e-mail pour membres ou non-membres
   - Gestion des invitations (acceptation/refus/révocation)

5. **Gérer les partenaires externes** (`/manage-external-partners`)
   - Ajouter des PR Agencies ou PR Consultants comme prestataires
   - Validation bilatérale : client invite → agence accepte/refuse
   - Impact sur la facturation de l'agence (ajout à la liste des clients)
   - L'agence nomme ensuite ses employés comme BWMe/BWPRe
   - Non disponible pour le type "BW for PR"

6. **Attribuer des missions** (`/assign-missions`)
   - Interface RBAC avec toggles Oui/Non pour chaque permission
   - Permissions disponibles :
     - Publier des communiqués de presse
     - Publier des événements
     - Publier des missions
     - Publier des projets
     - Publier des offres de stage
     - Publier des offres d'alternance
     - Publier des offres de convention doctorale
   - Résumé en temps réel des permissions activées

7. **Configurer le contenu** (`/configure-content`)
   - Formulaire dynamique adapté au type de BW
   - Sections communes : graphisme (logo, bandeau, galerie), contacts
   - Sections spécifiques par type :
     - Media : CPPAP, positionnement éditorial, périodicité
     - PR : type d'agence, liste des clients, secteurs
     - Leaders & Experts/Transformers : type d'organisation, taille, secteurs
     - Academics : établissement, domaines de recherche
   - Upload de fichiers (logo, images)
   - Géolocalisation et informations de contact

**Types de Business Wall GRATUITS** (5):
- **Business Wall for Media**: Pour organes de presse reconnus
- **Business Wall for Micro**: Pour micro-entreprises de presse travaillant pour des organes reconnus
- **Business Wall for Corporate Media**: Pour médias d'entreprise et institutionnels
- **Business Wall for Union**: Pour syndicats de presse et associations de journalistes
- **Business Wall for Academics**: Pour universités, écoles de journalisme et centres de recherche

**Types de Business Wall PAYANTS** (3):
- **Business Wall for PR**: Pour agences de RP (tarification par nombre de clients)
- **Business Wall for Leaders & Experts**: Pour entreprises et experts (tarification par nombre de salariés)
- **Business Wall for Transformers**: Pour acteurs de l'innovation (tarification par nombre de salariés)

**Fonctionnalités**:
- **Workflow complet en 7 étapes** du choix de l'abonnement à la configuration du BW
- **Dashboard de gestion** central après activation
- Page d'onboarding avec confirmation du type d'abonnement
- Messages détaillés pour chaque type de BW (conditions, CGV, validation)
- Formulaire de nomination des responsables (Owner + Paying Party)
- Pré-remplissage intelligent et duplication des coordonnées
- Workflows distincts pour activations gratuites et payantes
- **Gestion des rôles internes** (BWMi et BWPRi) avec simulation d'invitations
- **Gestion des partenaires externes** (PR Agencies) avec validation bilatérale
- **Attribution de permissions granulaires** (missions) avec toggles interactifs
- **Configuration de contenu dynamique** adaptée au type de BW
- Pages de confirmation personnalisées selon le type de BW
- Simulation de paiement avec calcul dynamique des tarifs
- Validation visuelle complète pour présentation client
- Utilisation d'Alpine.js pour l'interactivité (toggles, affichage conditionnel)
- Navigation cohérente avec boutons "Retour" contextuels
- Distinction "PR Manager" vs "Press Manager" pour le type Union

## Ajouter un nouveau POC

1. Créer un nouveau blueprint dans `src/poc/blueprints/`:
```python
# src/poc/blueprints/mon_poc.py
from flask import Blueprint, render_template

bp = Blueprint("mon_poc", __name__, template_folder="../templates")

@bp.route("/")
def index():
    return render_template("mon_poc.html")
```

2. Créer le template dans `src/poc/templates/`:
```html
{% extends "layout.html" %}

{% block content %}
<!-- Contenu du POC -->
{% endblock %}
```

3. Enregistrer le blueprint dans `src/poc/app.py`:
```python
from poc.blueprints.mon_poc import bp as mon_poc_bp
app.register_blueprint(mon_poc_bp, url_prefix="/mon-poc")
```

4. Ajouter le POC à la page d'accueil dans `src/poc/templates/poc_index.html`

## Notes techniques

- Application Flask avec blueprints
- Montée dans le serveur principal via Starlette
- Utilise Flask session pour l'état (pas de base de données)
- Templates Jinja2 avec Tailwind CSS via CDN
- Indépendant de l'application principale (pas de dépendances sur les modèles)

### Architecture Modulaire (Business Wall Activation Full)

Le POC "Business Wall Activation Full" utilise une architecture modulaire en package pour une meilleure maintenabilité :

- **Séparation des responsabilités** : Configuration, utilitaires et routes séparés
- **Organisation par étape** : Chaque stage du workflow a son propre module (`stage1.py`, `stage2.py`, etc.)
- **Pattern Flask standard** : Routes top-level, blueprint importé directement, pas de wrapper functions
- **Extensibilité** : Facile d'ajouter de nouveaux types de BW ou de nouvelles étapes
- **Clarté** : Code organisé et facile à naviguer (modules numérotés)
- **Documentation** : README dédié dans le package `bw_activation_full/`

**Blueprint Pattern:**
```python
# Dans chaque module de route (ex: routes/stage1.py)
from .. import bp

@bp.route("/endpoint")
def handler():
    pass  # Routes enregistrées automatiquement via side effects
```

Cette structure facilite la transition vers la production en suivant les patterns de l'application principale.
