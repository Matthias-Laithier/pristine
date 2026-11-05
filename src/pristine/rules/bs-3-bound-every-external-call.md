# BS-3 Bound Every External Call

Every network, database, broker, inter-process, and subprocess call has an explicit finite timeout or cancellation deadline. An unavailable dependency never suspends application work indefinitely. Choose the bound from the latency budget of the operation and propagate cancellation when the caller gives up.

Retries are finite and fit inside the same total deadline. Retry an operation only when repeating it is safe, because it is idempotent or because the protocol provides an idempotency mechanism. A timeout is a failure. It never permits fabricating a successful result.

A process the user drives and ends is the exception: an editor, a pager, or an interactive shell opened on the user's terminal. It runs for as long as the user keeps it open, and a timeout would cut the user's work. Pass it the terminal and capture none of its output, so its interactive nature stays visible in the call.

## Bad

```python
from collections.abc import Mapping
from math import isfinite


def parse_exchange_rate(response):
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("response must be a mapping")

    rate = payload.get("rate")
    if type(rate) not in (int, float) or not isfinite(rate) or rate <= 0:
        raise ValueError("rate must be a positive number")
    return rate


class ExchangeRateUnavailable(Exception):
    pass


class ExchangeRateService:
    def __init__(self, http_client):
        self.http_client = http_client

    def fetch(self, currency):
        try:
            response = self.http_client.get(
                "https://rates.example/rates",
                params={"currency": currency},
            )
        except HttpClientUnavailable as error:
            raise ExchangeRateUnavailable from error
        return parse_exchange_rate(response)
```

An unavailable service can hold the caller forever because the operation has no declared bound.

## Good

```python
from collections.abc import Mapping
from math import isfinite


def parse_exchange_rate(response):
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("response must be a mapping")

    rate = payload.get("rate")
    if type(rate) not in (int, float) or not isfinite(rate) or rate <= 0:
        raise ValueError("rate must be a positive number")
    return rate


class ExchangeRateUnavailable(Exception):
    pass


class ExchangeRateService:
    def __init__(self, http_client):
        self.http_client = http_client

    def fetch(self, currency):
        try:
            response = self.http_client.get(
                "https://rates.example/rates",
                params={"currency": currency},
                timeout=3,
            )
        except HttpClientUnavailable as error:
            raise ExchangeRateUnavailable from error
        return parse_exchange_rate(response)
```

The call has a visible finite budget. If the dependency cannot respond within it, the operation fails and frees the caller. [BS-9](bs-9-boundaries-expose-stable-error-contracts.md) owns the failure the service boundary exposes.
