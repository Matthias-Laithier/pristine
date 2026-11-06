# BS-14 Bound Every Load, Response, and Fan-Out

The data and the concurrent work an operation handles have an explicit bound that does not grow with the data that exists. A query over a collection that grows with usage carries a limit or streams in batches. A list endpoint or agent tool paginates with a maximum page size. Related records load in one batched query, never one query per item of a loop. Concurrent fan-out over a collection runs through a bounded pool or semaphore.

Code tested on ten rows meets ten million in production. An unbounded load exhausts memory, an unpaginated response times out, an N+1 loop turns one query into a thousand, and an unbounded fan-out against a model provider turns into a storm of rate-limit failures.

The exceptions:
- Collections with a small fixed bound, such as the values of an enum or the lines of an order capped by a business rule. Name the bound.
- Batch jobs that must process everything. They iterate in bounded pages or streams and never hold the whole set at once.

[BS-1](bs-1-validate-untrusted-input-at-the-boundary.md) owns the size of incoming input. [BS-3](bs-3-bound-every-external-call.md) bounds time. This rule bounds quantity.

## Bad

```python
import asyncio


async def summarize_batch(document_store, summarizer, batch_id):
    documents = await document_store.list_documents(batch_id, timeout=3.0)
    async with asyncio.TaskGroup() as task_group:
        tasks = [task_group.create_task(summarizer.summarize(document)) for document in documents]
    return [task.result() for task in tasks]
```

A batch of five thousand documents opens five thousand concurrent model calls. The provider rate-limits the batch, and it fails as a whole.

## Good

```python
import asyncio

MAX_CONCURRENT_SUMMARIES = 8


async def summarize_batch(document_store, summarizer, batch_id):
    documents = await document_store.list_documents(batch_id, timeout=3.0)
    concurrency_limit = asyncio.Semaphore(MAX_CONCURRENT_SUMMARIES)

    async def summarize_within_limit(document):
        async with concurrency_limit:
            return await summarizer.summarize(document)

    async with asyncio.TaskGroup() as task_group:
        tasks = [task_group.create_task(summarize_within_limit(document)) for document in documents]
    return [task.result() for task in tasks]
```

At most eight calls run at once, whatever the size of the batch.
