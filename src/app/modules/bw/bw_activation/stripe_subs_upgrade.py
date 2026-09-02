# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helper to upgrade/change the Stripe product of a Business Wall subscription."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import stripe

from app.flask.extensions import db
from app.logging import warn
from app.modules.bw.bw_activation.bw_product import evaluate_subscription
from app.services.stripe.product import resolve_product_price
from app.services.stripe.utils import load_stripe_api_key

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


def _get_stripe_subscription(stripe_subscription_id: str) -> Any | None:
    """Retrieve a Stripe subscription by id.

    `None` means we could not read it, and the caller turns that into
    « Impossible de récupérer l'abonnement Stripe » for the operator.
    It used to swallow every exception without a word, so that message
    was the only trace an outage left.
    """
    if not load_stripe_api_key():
        warn(
            f"Cannot retrieve Stripe subscription {stripe_subscription_id!r}: "
            "Stripe API key not found"
        )
        return None
    try:
        return stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.StripeError as e:
        warn(f"Failed to retrieve Stripe subscription {stripe_subscription_id!r}: {e}")
        return None


def _find_item_to_replace(stripe_sub: Any) -> str | None:
    """Return the first subscription item id.

    A Stripe `Subscription.items` is a `ListObject` carrying `.data`;
    both it and the items inside also answer to bracket access, which
    is what the CLI fixtures hand us.
    """
    items = _get_key(stripe_sub, "items")
    data = _get_key(items, "data") if items is not None else None
    if not data:
        return None
    return _get_key(data[0], "id")


def _get_key(obj: Any, key: str) -> Any:
    """Read `key` off a Stripe object or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


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
    except stripe.StripeError as e:
        warn(f"Failed to change subscription {stripe_subscription_id!r}: {e}")
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
