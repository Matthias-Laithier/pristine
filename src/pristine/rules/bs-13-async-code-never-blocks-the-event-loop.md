# BS-13 Async Code Never Blocks the Event Loop

Inside a coroutine, every call that waits on I/O, sleeps, or computes for long is awaited through an asynchronous API or offloaded to a worker thread or process. Never call a synchronous HTTP client, database driver, SDK method, `time.sleep`, blocking subprocess API, or CPU-heavy function directly in asynchronous code.

One event loop serves every concurrent request. A single blocking call stalls all of them, and no timeout on the loop can fire while it runs, the deadlines of [BS-3](bs-3-bound-every-external-call.md) included.

The exceptions:
- Local operations with a small, bounded cost, such as in-memory computation within the latency budget or reading a small file at startup.
- Libraries with only a synchronous API. Wrap each call with `asyncio.to_thread` or the ecosystem equivalent inside the service of the library (see [CO-6](co-6-wrap-external-clients-in-singleton-services.md)), so callers await a coroutine.

[BS-8](bs-8-resources-have-explicit-owners-and-lifetimes.md) owns releasing what a coroutine acquires. This rule owns what a coroutine may do on the loop.

## Bad

```python
import time

RETRY_DELAY_IN_SECONDS = 2


async def fetch_exchange_rate_with_retry(exchange_rate_service, currency):
    try:
        return await exchange_rate_service.fetch(currency)
    except ExchangeRateUnavailable:
        time.sleep(RETRY_DELAY_IN_SECONDS)
        return await exchange_rate_service.fetch(currency)
```

Every request served by the process freezes for two seconds whenever one rate lookup retries.

## Good

```python
import asyncio

RETRY_DELAY_IN_SECONDS = 2


async def fetch_exchange_rate_with_retry(exchange_rate_service, currency):
    try:
        return await exchange_rate_service.fetch(currency)
    except ExchangeRateUnavailable:
        await asyncio.sleep(RETRY_DELAY_IN_SECONDS)
        return await exchange_rate_service.fetch(currency)
```

The retry waits without holding the loop, and concurrent requests keep running.
