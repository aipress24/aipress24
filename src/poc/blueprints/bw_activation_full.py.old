# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall Activation Full - Complete workflow with all BW types.

This blueprint demonstrates the complete Business Wall activation workflow:
- Free activation for 5 types (Media, Micro, Corporate Media, Union, Academics)
- Paid activation for 3 types (PR, Leaders & Experts, Transformers)
- Role assignment after activation
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

bp = Blueprint("bw_activation_full", __name__, template_folder="../templates")

# Business Wall Types configuration
BW_TYPES = {
    # Free BW types (5 types)
    "media": {
        "name": "Business Wall for Media",
        "description": "Pour les organes de presse reconnus.",
        "free": True,
        "activation_text": "Approuver l'accord de diffusion sur AiPRESS24 + Business Wall CGV",
        "manager_role": "PR Manager",  # For confirmation messages
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Media sera la vitrine sur AiPRESS24 de l'organe de presse reconnu que vous dirigez.",
            "Vous devez créer un seul Business Wall for Media par organe de presse.",
            "Pour bénéficier de votre Business Wall for Media, de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital, etc.) et pour commercialiser vos contenus journalistiques (consultations sur NEWS, Consultations Offertes, justificatifs de publication, revente de ©, fonds mutualisé des Avis d'enquêtes), vous devrez approuver notre contrat de diffusion sur AiPRESS24.",
            "Vous devrez aussi approuver nos Conditions générales de vente sur AiPRESS24.",
            "Vous devez également déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "micro": {
        "name": "Business Wall for Micro",
        "description": "Pour les micro-entreprises de presse travaillant pour des organes de presse reconnus.",
        "free": True,
        "activation_text": "Approuver l'accord de diffusion sur AiPRESS24 + Business Wall CGV",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Micro sera la vitrine sur AiPRESS24 de votre micro-entreprise de presse travaillant pour des organes de presse reconnus.",
            "Pour bénéficier de Business Wall for Micro, de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital, etc.) et pour commercialiser vos contenus journalistiques (consultations sur NEWS, Consultations Offertes, justificatifs de publication, revente de ©, fonds mutualisé des Avis d'enquêtes), vous devrez approuver notre contrat de diffusion sur AiPRESS24.",
            "Vous devrez aussi approuver nos Conditions générales de vente sur AiPRESS24.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "corporate_media": {
        "name": "Business Wall for Corporate Media",
        "description": "Pour les médias d'entreprise et institutionnels.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Corporate Media sera la vitrine sur AiPRESS24 de votre organe de presse institutionnel",
            "Pour bénéficier de Business Wall for Corporate Media et de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital), vous devrez approuver nos Conditions générales de vente.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "union": {
        "name": "Business Wall for Union",
        "description": "Pour les syndicats ou fédérations de la presse ou des médias, clubs de la presse ou associations de journalistes.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "Press Manager",  # Different from other types
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Union sera la vitrine sur AiPRESS24 de votre syndicat ou fédération de la presse ou des médias, de votre club de la presse ou association de journalistes",
            "Pour bénéficier de Business Wall for Union, vous devrez approuver nos Conditions générales de vente.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
            "Vous devez déclarer également déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
        ],
    },
    "academics": {
        "name": "Business Wall for Academics",
        "description": "Pour les établissements de recherche ou d'enseignement supérieur.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Academics sera la vitrine sur AiPRESS24 de votre établissement de recherche ou d'enseignement supérieur",
            "Pour bénéficier de Business Wall for Academics, vous devrez approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    # Paid BW types
    "pr": {
        "name": "Business Wall for PR",
        "description": "Pour les agences de relations presse et les consultants indépendants.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "client_count",
        "pricing_label": "Nombre de clients représentés",
        "pricing_placeholder": "Ex: 5",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for PR sera la vitrine sur AiPRESS24 de votre PR Agency ou de votre activité de PR Consultant indépendant.e",
            "Pour bénéficier de Business Wall for PR, vous devez déclarer le nombre de vos clients que vous représentez sur AiPRESS24 car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous pourrez représenter vos clients sur AiPRESS24, agir en tant que contact presse, publier leurs communiqués de presse et leurs événements après que chacun de vos clients aura déclaré et validé votre organisation sur AiPRESS24.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "leaders_experts": {
        "name": "Business Wall for Leaders & Experts",
        "description": "Pour les entreprises, associations, experts et leaders d'opinion.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "employee_count",
        "pricing_label": "Nombre de salariés",
        "pricing_placeholder": "Ex: 50",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for Leaders & Experts (BW4L&E) sera la vitrine de votre groupe, entreprise privée, administration, ministère ou association sur AiPRESS24",
            "Pour bénéficier du BW4L&E, vous devez déclarer le nombre de vos salariés car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "transformers": {
        "name": "Business Wall for Transformers",
        "description": "Pour les acteurs de l'innovation et de la transformation numérique.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "employee_count",
        "pricing_label": "Nombre de salariés",
        "pricing_placeholder": "Ex: 20",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for Transformers (BW4T) sera la vitrine de votre groupe, entreprise privée, administration, ministère ou association sur AiPRESS24",
            "Pour bénéficier du BW4T, vous devez déclarer le nombre de vos salariés car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
}


def init_session():
    """Initialize session with default values if not set."""
    if "bw_type" not in session:
        session["bw_type"] = None
    if "bw_type_confirmed" not in session:
        session["bw_type_confirmed"] = False
    if "suggested_bw_type" not in session:
        session["suggested_bw_type"] = "media"  # Default suggestion based on KYC
    if "contacts_confirmed" not in session:
        session["contacts_confirmed"] = False
    if "bw_activated" not in session:
        session["bw_activated"] = False
    if "pricing_value" not in session:
        session["pricing_value"] = None


@bp.route("/")
def index():
    """Redirect to confirmation subscription page."""
    init_session()
    return redirect(url_for("bw_activation_full.confirm_subscription"))


@bp.route("/confirm-subscription")
def confirm_subscription():
    """Step 1: Confirm or change subscription type."""
    init_session()
    suggested_type = session.get("suggested_bw_type", "media")
    return render_template(
        "bw_activation_full/00_confirm_subscription.html",
        bw_types=BW_TYPES,
        suggested_bw_type=suggested_type,
    )


@bp.route("/select-subscription/<bw_type>", methods=["POST"])
def select_subscription(bw_type):
    """Confirm or select a subscription type and redirect to contacts nomination."""
    if bw_type not in BW_TYPES:
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    session["bw_type"] = bw_type
    session["bw_type_confirmed"] = True

    # After subscription selection, go to contacts nomination
    return redirect(url_for("bw_activation_full.nominate_contacts"))


@bp.route("/nominate-contacts")
def nominate_contacts():
    """Step 2: Nominate Business Wall Owner and Paying Party."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    bw_type = session.get("bw_type")
    bw_info = BW_TYPES.get(bw_type, {})

    # Pre-fill with mock user data (in real app, use current_user)
    owner_data = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "email": "alice.dupont@example.com",
        "phone": "+33 1 23 45 67 89",
    }

    return render_template(
        "bw_activation_full/02_nominate_contacts.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_data=owner_data,
    )


@bp.route("/submit-contacts", methods=["POST"])
def submit_contacts():
    """Process contacts nomination and redirect to activation."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    # Store contact information in session
    session["owner_first_name"] = request.form.get("owner_first_name")
    session["owner_last_name"] = request.form.get("owner_last_name")
    session["owner_email"] = request.form.get("owner_email")
    session["owner_phone"] = request.form.get("owner_phone")

    same_as_owner = request.form.get("same_as_owner") == "on"
    if same_as_owner:
        session["payer_first_name"] = session["owner_first_name"]
        session["payer_last_name"] = session["owner_last_name"]
        session["payer_email"] = session["owner_email"]
        session["payer_phone"] = session["owner_phone"]
    else:
        session["payer_first_name"] = request.form.get("payer_first_name")
        session["payer_last_name"] = request.form.get("payer_last_name")
        session["payer_email"] = request.form.get("payer_email")
        session["payer_phone"] = request.form.get("payer_phone")

    session["contacts_confirmed"] = True

    # Redirect to appropriate activation page based on BW type
    bw_type = session.get("bw_type")
    if BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.activate_free_page", bw_type=bw_type))
    else:
        return redirect(url_for("bw_activation_full.pricing_page", bw_type=bw_type))


@bp.route("/activate-free/<bw_type>")
def activate_free_page(bw_type):
    """Step 3: Page for free BW activation with CGV acceptance."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation_full.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation_full/activate_free.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/pricing/<bw_type>")
def pricing_page(bw_type):
    """Step 3: Page for paid BW pricing information."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation_full.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation_full/pricing.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/activation-choice")
def activation_choice():
    """Step 2: Business Wall activation page (all types - for visual validation)."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    return render_template("bw_activation_full/01_activation_choice.html", bw_types=BW_TYPES)


@bp.route("/activate_free/<bw_type>", methods=["POST"])
def activate_free(bw_type):
    """Process free Business Wall activation."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.index"))

    cgv_accepted = request.form.get("cgv_accepted") == "on"
    if cgv_accepted:
        session["bw_type"] = bw_type
        session["bw_activated"] = True
        return redirect(url_for("bw_activation_full.confirmation_free"))

    return redirect(url_for("bw_activation_full.activate_free_page", bw_type=bw_type))


@bp.route("/set_pricing/<bw_type>", methods=["POST"])
def set_pricing(bw_type):
    """Set pricing information for paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.index"))

    pricing_field = BW_TYPES[bw_type]["pricing_field"]
    try:
        pricing_value = int(request.form.get(pricing_field, 0))
        if pricing_value > 0:
            session["bw_type"] = bw_type
            session["pricing_value"] = pricing_value
            return redirect(url_for("bw_activation_full.payment", bw_type=bw_type))
    except ValueError:
        pass

    return redirect(url_for("bw_activation_full.index"))


@bp.route("/payment/<bw_type>")
def payment(bw_type):
    """Payment page for paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.index"))

    if not session.get("pricing_value"):
        return redirect(url_for("bw_activation_full.index"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation_full/payment.html",
        bw_type=bw_type,
        bw_info=bw_info,
        pricing_value=session["pricing_value"],
    )


@bp.route("/simulate_payment/<bw_type>", methods=["POST"])
def simulate_payment(bw_type):
    """Simulate payment and activate paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation_full.index"))

    if session.get("pricing_value"):
        session["bw_activated"] = True
        return redirect(url_for("bw_activation_full.confirmation_paid"))

    return redirect(url_for("bw_activation_full.index"))


@bp.route("/confirmation/free")
def confirmation_free():
    """Confirmation page for free BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/02_activation_gratuit_confirme.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/confirmation/paid")
def confirmation_paid():
    """Confirmation page for paid BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/03_activation_payant_confirme.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/dashboard")
def dashboard():
    """Business Wall management dashboard (after activation)."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/dashboard.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/manage-internal-roles")
def manage_internal_roles():
    """Stage 4: Manage internal Business Wall Managers and PR Managers."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/04_manage_internal_roles.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/manage-external-partners")
def manage_external_partners():
    """Stage 5: Manage external PR Agencies and Consultants."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/05_manage_external_partners.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/assign-missions")
def assign_missions():
    """Stage 6: Assign permissions/missions to PR Managers."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    # Initialize missions state in session if not present
    if "missions" not in session:
        session["missions"] = {
            "press_release": False,
            "events": False,
            "missions": False,
            "projects": False,
            "internships": False,
            "apprenticeships": False,
            "doctoral": False,
        }

    return render_template(
        "bw_activation_full/06_assign_missions.html",
        bw_type=bw_type,
        bw_info=bw_info,
        missions=session["missions"],
    )


@bp.route("/configure-content")
def configure_content():
    """Stage 7: Configure Business Wall content."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/07_configure_content.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    return redirect(url_for("bw_activation_full.index"))
