# CO-13 Imports Do Not Perform External Work

Importing a module never connects to a service, reads a file, inspects environment configuration, starts a thread, registers a signal handler, writes output, or performs application work. Imports define values, functions, classes, and controlled in-memory declarations. Runtime setup happens through an explicit function that the composition root calls.

Work at import time makes module loading depend on the environment and on import order. It prevents tests from supplying configuration before construction and can leave partially initialized state after a failure. [CO-9](co-9-keep-side-effects-at-the-edges.md) owns where effects belong. This rule owns what happens when a module loads.

The exceptions:
- Pure constants and deterministic construction from literals.
- Framework-mandated declarations, when the framework explicitly treats import as configuration.

## Bad

```python
import os

PAYMENTS_CREDENTIAL = os.environ["PAYMENTS_API_KEY"]
```

Importing the module reads process state. Tests and tools cannot inspect it without valid production configuration.

## Good

```python
from payments_sdk import PaymentsClient


def create_payments_client(credential):
    return PaymentsClient(credential)
```

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class PaymentsSettings(BaseSettings):
    payments_api_key: SecretStr


def main():
    payments_settings = PaymentsSettings()
    payments_api_key = payments_settings.payments_api_key.get_secret_value()
    with create_payments_client(payments_api_key) as payments_client:
        run_application(payments_client)
```

The module is safe to import anywhere. The composition root builds the settings and the client explicitly.
