# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Script to delete all Stripe Products and Prices.

DESTRUCTIVE : this removes every product and archives every price from the
target Stripe account. Stripe prices are immutable and can only be archived
(active=False).
"""

from __future__ import annotations

import traceback

import stripe

# Target Stripe secret key (test or live).
TARGET_SECRET_KEY = "sk_test_xxx"  # noqa: S105


def _archive_prices_for_product(product: stripe.Product) -> tuple[int, list[str]]:
    """Archive (deactivate) all prices attached to a product."""
    archived = 0
    errors: list[str] = []

    # A price that is the product's default_price cannot be archived.
    # Clear the default price first.
    if getattr(product, "default_price", None):
        try:
            stripe.Product.modify(product.id, default_price=None)
            print("   └─ Cleared default price")
        except Exception as e:
            errors.append(f"Product {product.id} clear default_price: {e}")
            print(f"   └─ [ERROR] Could not clear default price: {e}")

    prices = stripe.Price.list(product=product.id)
    for price in prices.auto_paging_iter():
        if not price.active:
            continue
        try:
            stripe.Price.modify(price.id, active=False)
            archived += 1
            print(f"   └─ Archived price {price.id}")
        except Exception as e:
            errors.append(f"Price {price.id}: {e}")
            print(f"   └─ [ERROR] Could not archive price {price.id}: {e}")

    return archived, errors


def delete_all_products() -> dict:
    """Delete all products and archive all prices from Stripe."""
    products_deleted = 0
    products_archived = 0
    prices_archived = 0
    errors: list[str] = []

    products = stripe.Product.list()
    product_list = list(products.auto_paging_iter())

    print(f"Found {len(product_list)} product(s) to clean up.\n")

    for idx, product in enumerate(product_list, start=1):
        print(f"[{idx:>3}/{len(product_list)}] Product: {product.name} ({product.id})")

        # 1. Archive prices attached to the product
        price_count, price_errors = _archive_prices_for_product(product)
        prices_archived += price_count
        errors.extend(price_errors)

        # 2. Delete the product itself; if deletion fails, archive it instead
        try:
            stripe.Product.delete(product.id)
            products_deleted += 1
            print(f"   Deleted product {product.id}")
        except Exception as e:
            try:
                stripe.Product.modify(product.id, active=False)
                products_archived += 1
                print(f"   Archived product {product.id}")
            except Exception as archive_error:
                errors.append(
                    f"Product {product.id}: {e} / archive fallback: {archive_error}"
                )
                print(
                    f"   [ERROR] Could not delete or archive product {product.id}: {archive_error}"
                )

    return {
        "products_found": len(product_list),
        "products_deleted": products_deleted,
        "products_archived": products_archived,
        "prices_archived": prices_archived,
        "errors": errors,
    }


def main() -> None:
    stripe.api_key = TARGET_SECRET_KEY

    print("=" * 60)
    print("WARNING: This will delete ALL products and archive ALL prices in Stripe.")
    print("=" * 60)

    confirmation = input("Type 'DELETE' to confirm: ").strip()
    if confirmation != "DELETE":
        print("Aborted.")
        return

    try:
        summary = delete_all_products()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return

    print("\n=== Summary ===")
    print(f"Products found    : {summary['products_found']}")
    print(f"Products deleted  : {summary['products_deleted']}")
    print(f"Products archived : {summary['products_archived']}")
    print(f"Prices archived   : {summary['prices_archived']}")
    print(f"Errors            : {len(summary['errors'])}")

    if summary["errors"]:
        print("\nError details:")
        for err in summary["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
