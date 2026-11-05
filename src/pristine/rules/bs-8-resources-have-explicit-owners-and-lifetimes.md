# BS-8 Resources Have Explicit Owners and Lifetimes

Every resource that requires release has one explicit owner and a bounded lifetime. Files, streams, locks, transactions, temporary directories, subprocesses, threads, asynchronous tasks, promises, sockets, and external clients are closed, committed, rolled back, joined, awaited, terminated, or otherwise released on every path, failure paths included. A spawned task is awaited by its owner, and a handler of cancellation re-raises it.

Use the language's structured lifetime mechanism, such as a context manager, a scoped guard, or `try` and `finally`. The code that acquires a resource owns its release unless the interface explicitly transfers ownership. Never return a live resource whose interface leaves its cleanup unstated. A context manager, or a factory named for what it opens such as `open_invoice_archive`, states it.

The composition root may create application-lifetime resources and close them during shutdown. Shared pools and clients follow [CO-6](co-6-wrap-external-clients-in-singleton-services.md). A process ending at some point is no cleanup strategy.

## Tasks and promises
A spawned task is owned and awaited. Use structured concurrency: `asyncio.TaskGroup`, an equivalent nursery, or a reference the owner keeps and awaits before its scope ends. Never create a task and drop it, whether through a fire-and-forget `create_task`, an `ensure_future`, or an unawaited promise. A dropped task loses its exception, can be garbage-collected while it runs, and outlives the operation that started it.

Never swallow cancellation. A handler of `asyncio.CancelledError`, or of the cancellation signal of another ecosystem, re-raises it after cleanup. A swallowed cancellation keeps a task running after its owner gave up, and breaks the deadlines of [BS-3](bs-3-bound-every-external-call.md) and the shutdown of every task group above it.

[BS-13](bs-13-async-code-never-blocks-the-event-loop.md) owns blocking the event loop. This rule owns the lifetime of the tasks that run on it.

## Bad: file

```python
def read_invoice(path):
    invoice_file = open(path, encoding="utf-8")
    return invoice_file.read()
```

The function acquires the file and never closes it. An exception during reading leaks the resource as readily as a successful return.

## Good: file

```python
def read_invoice(path):
    with open(path, encoding="utf-8") as invoice_file:
        return invoice_file.read()
```

The acquiring scope owns the file. It closes on successful return and on every exception path.

## Bad: task

```python
import asyncio


async def complete_order(receipt_mailer, loyalty_service, order):
    asyncio.create_task(receipt_mailer.send_receipt(order))
    asyncio.create_task(loyalty_service.award_points(order))
```

Nothing holds the tasks. The function returns before either finishes, a failure to send the receipt vanishes, and a shutdown cancels the award of points without a trace.

## Good: task

```python
import asyncio


async def complete_order(receipt_mailer, loyalty_service, order):
    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(receipt_mailer.send_receipt(order))
        task_group.create_task(loyalty_service.award_points(order))
```

The task group owns both tasks. The function returns once both finish, and a failure in either cancels the other and propagates to the caller.
