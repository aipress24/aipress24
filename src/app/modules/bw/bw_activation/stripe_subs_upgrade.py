# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helper to upgrade/change the Stripe product of a Business Wall subscription."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import stripe

from app.flask.extensions import db
from app.modules.bw.bw_activation.bw_product import evaluate_subscription
from app.services.stripe.product import resolve_product_price
from app.services.stripe.utils import load_stripe_api_key

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


def _get_stripe_subscription(stripe_subscription_id: str) -> Any | None:
    """Retrieve a Stripe subscription by id."""
    if not load_stripe_api_key():
        return None
    try:
        return stripe.Subscription.retrieve(stripe_subscription_id)
    except Exception:
        return None


def _find_item_to_replace(stripe_sub: Any) -> str | None:
    """Return the first subscription item id."""
    items = getattr(stripe_sub, "items", None)
    if items is None:
        return None
    data = (
        getattr(items, "data", None)
        if not isinstance(items, dict)
        else items.get("data")
    )
    if not data:
        return None
    first_item = data[0]
    if isinstance(first_item, dict):
        return first_item.get("id")
    return getattr(first_item, "id", None)


def change_bw_subscription_tier(
    bw: BusinessWall,
    target_quantity: int | None,
) -> dict[str, Any]:
    """Change the Stripe subscription of a BW to the product matching "target_quantity"."""
    result: dict[str, Any] = {
        "success": False,
        "message": "",
        "tier": None,
        "stripe_subscription_id": None,
    }

    sub = bw.subscription
    if sub is None:
        result["message"] = "Aucun abonnement local trouvé pour ce Business Wall."
        return result

    stripe_subscription_id = sub.stripe_subscription_id
    if not stripe_subscription_id:
        result["message"] = "Aucun abonnement Stripe trouvé pour ce Business Wall."
        return result

    evaluation = evaluate_subscription(bw, target_quantity)
    if evaluation.get("ok"):
        result["success"] = True
        result["message"] = "Aucun changement d'abonnement requis."
        result["tier"] = evaluation.get("current_tier")
        return result

    recommended_product = evaluation.get("recommended_product")
    if recommended_product is None:
        result["message"] = "Impossible de déterminer le produit Stripe recommandé."
        return result

    new_price_id, _ = resolve_product_price(recommended_product)
    if not new_price_id:
        result["message"] = "Le produit Stripe recommandé n'a pas de prix actif."
        return result

    stripe_sub = _get_stripe_subscription(stripe_subscription_id)
    if stripe_sub is None:
        result["message"] = "Impossible de récupérer l'abonnement Stripe."
        return result

    item_id = _find_item_to_replace(stripe_sub)
    if not item_id:
        result["message"] = "Aucun item d'abonnement Stripe trouvé à remplacer."
        return result

    try:
        updated_sub = stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{"id": item_id, "price": new_price_id}],
            proration_behavior="create_prorations",
        )
    except Exception as e:
        result["message"] = f"Erreur Stripe lors du changement d'abonnement : {e}"
        return result

    new_tier = evaluation.get("recommended_tier") or ""
    sub.pricing_tier = str(new_tier)
    sub.pricing_field = "employee_count"

    db.session.commit()

    result["success"] = True
    result["message"] = f"L'abonnement a été changé vers la catégorie {new_tier}."
    result["tier"] = new_tier
    result["stripe_subscription_id"] = updated_sub.id
    return result
