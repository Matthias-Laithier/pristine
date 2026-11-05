# BS-2 Keep Secrets Out of Code and Output

Secrets never enter source code, committed configuration, logs, error messages, URLs, test fixtures, snapshots, or generated artifacts. Load credentials, tokens, private keys, and other secrets from the runtime environment or an approved secret provider. Pass them only to the component that needs them and redact them from every observable output.

Use visibly fake, non-functional values in tests. Public identifiers and configuration values are no secrets merely because they come from the environment. If a real secret is exposed, revoke or rotate it at once. Removing it from the file does not make the exposed value safe again.

## Bad

```python
PAYMENTS_CREDENTIAL = "live_4f8c2a7e"


class PaymentsService:
    def __init__(self, payments_client, activity_log):
        self.payments_client = payments_client
        self.activity_log = activity_log

    def charge_customer(self, customer_identifier, amount_in_cents):
        self.activity_log.write(f"Charging with {PAYMENTS_CREDENTIAL}")
        response = self.payments_client.charge(
            credential=PAYMENTS_CREDENTIAL,
            customer_identifier=customer_identifier,
            amount_in_cents=amount_in_cents,
            timeout=3,
        )
        return parse_payment_receipt(response)
```

The secret is committed and copied into logs. Deleting the log line later cannot retract either exposure.

## Good

```python
import os


def create_payments_service(payments_client):
    return PaymentsService(
        payments_client,
        credential=os.environ["PAYMENTS_API_KEY"],
    )
```

The secret enters only at runtime and goes directly to its owner. It is never rendered or stored in source control.
