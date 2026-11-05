# CR-10 Business Logic Lives in the Backend

In a client-server application, the frontend owns display, navigation, interaction state, and user input. The backend owns every authoritative business decision: validation, authorization, pricing, eligibility, permissions, state transitions, workflows, and persistence. The frontend renders decisions returned by the backend and makes none itself.

The frontend may validate input shape for immediate feedback, such as required fields or number formats. The backend performs the authoritative validation. Display formatting, sorting visible data, and local interface behavior are no business logic. A rule that changes what the business allows, charges, stores, or promises belongs only in the backend.

Never duplicate a business rule in the frontend. If the interface needs to know whether an action is allowed or what an outcome will be, it asks the backend or consumes a capability, status, or quote the backend provides. Hiding a button is presentation. It authorizes nothing.

## Bad

`frontend/checkout.ts`:

```typescript
const GOLD_CUSTOMER_TIER = "gold";
const GOLD_DISCOUNT_IN_BASIS_POINTS = 1_000;
const BASIS_POINTS_PER_UNIT = 10_000;

function calculateTotalInCents(cart, customer) {
  const discountInBasisPoints =
    customer.tier === GOLD_CUSTOMER_TIER
      ? GOLD_DISCOUNT_IN_BASIS_POINTS
      : 0;
  const subtotalInCents = cart.lines.reduce(
    (total, line) => total + line.unitPriceInCents * line.quantity,
    0,
  );
  return (
    subtotalInCents
    - Math.floor(
      subtotalInCents * discountInBasisPoints / BASIS_POINTS_PER_UNIT,
    )
  );
}
```

The frontend decides who receives a discount and how much they pay. Another client can implement a different rule, and changing the business policy requires coordinated frontend releases.

## Good

`backend/pricing.py`:

```python
GOLD_CUSTOMER_TIER = "gold"
GOLD_DISCOUNT_IN_BASIS_POINTS = 1_000
BASIS_POINTS_PER_UNIT = 10_000


def quote_order(order, customer):
    discount_in_basis_points = GOLD_DISCOUNT_IN_BASIS_POINTS if customer.tier == GOLD_CUSTOMER_TIER else 0
    subtotal_in_cents = sum(line.unit_price_in_cents * line.quantity for line in order.lines)
    total_in_cents = subtotal_in_cents - subtotal_in_cents * discount_in_basis_points // BASIS_POINTS_PER_UNIT
    return OrderQuote(total_in_cents=total_in_cents)
```

`frontend/checkout.ts`:

```typescript
async function renderCheckout(checkoutService, quoteRequest) {
  const quote = await checkoutService.quote(quoteRequest);
  return formatCurrency(quote.totalInCents);
}
```

The backend owns the discount and the total. The frontend sends input, receives the authoritative quote through its service boundary, and formats it for display.

See [BS-1](bs-1-validate-untrusted-input-at-the-boundary.md) for authoritative input validation and [CO-9](co-9-keep-side-effects-at-the-edges.md) for frontend and backend service boundaries.
