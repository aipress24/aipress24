# Stripe

Part of [Lessons Learned](00-index.md).

### Never hit the Stripe API at render time for a displayed price

**Rule**: mirror prices locally, fed by `price.created/updated/deleted` webhooks.

Any cache window between Stripe's authoritative price and the displayed one is a risk that the user pays an amount other than the one shown. The Checkout page remains the final authority on what's charged.
