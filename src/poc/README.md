# POC - Prototypes et Expérimentations

Ce répertoire contient une application Flask pour prototyper et valider des concepts (POC - Proof of Concept) avant intégration dans l'application principale.

## Structure

```
src/poc/
├── app.py                    # Application Flask principale
├── blueprints/               # Blueprints pour chaque POC
│   ├── __init__.py
│   └── bw_activation.py     # Business Wall Activation POC
└── templates/                # Templates Jinja2
    ├── layout.html           # Layout de base
    ├── poc_index.html        # Page d'accueil du POC
    └── bw_activation.html    # Template BW activation
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

**Workflow d'activation en 4 étapes**:

1. **Confirmation d'abonnement** (`/confirm-subscription`)
   - Le système suggère un type de BW basé sur le profil KYC
   - Affichage des messages d'onboarding détaillés (conditions, tarification, validation)
   - Possibilité de confirmer le type suggéré ou d'en choisir un autre
   - Interface interactive avec Alpine.js

2. **Nomination des responsables** (`/nominate-contacts`) ⭐ NOUVEAU
   - Désignation du Business Wall Owner (dirigeant décisionnaire)
   - Désignation du contact de facturation (Paying Party)
   - Pré-remplissage intelligent avec les données de l'utilisateur connecté
   - Option pour dupliquer les coordonnées (Owner = Payeur)
   - Formulaire avec validation des champs obligatoires

3. **Activation/Tarification**
   - Pour les BW gratuits : Acceptation des CGV et du contrat de diffusion
   - Pour les BW payants : Saisie des informations de tarification (nb de clients ou salariés)

4. **Confirmation finale**
   - Message de succès personnalisé selon le type de BW
   - Attribution automatique du rôle "Business Wall Owner"
   - Invitation à gérer le Business Wall (désignation des managers)

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
- Page d'onboarding avec confirmation du type d'abonnement
- Messages détaillés pour chaque type de BW (conditions, CGV, validation)
- Formulaire de nomination des responsables (Owner + Paying Party)
- Pré-remplissage intelligent et duplication des coordonnées
- Workflows distincts pour activations gratuites et payantes
- Pages de confirmation personnalisées selon le type de BW
- Simulation de paiement avec calcul dynamique des tarifs
- Validation visuelle complète pour présentation client
- Utilisation d'Alpine.js pour l'interactivité (affichage conditionnel)
- Navigation cohérente avec boutons "Retour" contextuels

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
