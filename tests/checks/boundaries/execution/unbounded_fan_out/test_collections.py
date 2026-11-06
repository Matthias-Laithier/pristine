import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-14"
UNBOUNDED_FAN_OUTS = """import asyncio

from archive import list_documents


async def summarize_archive(summarizer):
    documents = await list_documents()
    return await asyncio.gather(*(summarizer.summarize(document) for document in documents))


async def delete_blobs(storage, prefix):
    blobs_list = await storage.list_blobs(prefix=prefix)
    await asyncio.gather(*[storage.delete(blob.name) for blob in blobs_list])


async def fetch_invoices(client):
    return await asyncio.gather(*map(client.fetch_invoice, await client.list_invoice_ids()))


async def notify_members(notifier, directory):
    async with asyncio.TaskGroup() as task_group:
        for member in await directory.list_members():
            task_group.create_task(notifier.notify(member))


class Exporter:
    def __init__(self, store):
        self.store = store

    async def export_stored(self, exporter):
        stored = await self.store.list_records()
        kept = [record for record in stored if record.kept]
        await asyncio.gather(*(exporter.export(record) for record in kept))

    async def export_held(self, exporter):
        held = {record.key: record for record in await self.store.list_records()}
        await asyncio.gather(*(exporter.export(record) for record in held.values()))
"""
UNBOUNDED_LINES = [(8, "warning"), (13, "warning"), (17, "warning"), (23, "warning"), (33, "warning")]
UNBOUNDED_LINES += [(37, "warning")]
BOUNDED_FAN_OUTS = """import asyncio

from billing import ReportKind

REGIONS = ("eu", "us")
PAGE_SIZE = 50


async def warm_regions(cache):
    await asyncio.gather(*(cache.warm(region) for region in ("eu", "us", "asia")))
    await asyncio.gather(*(cache.warm(region) for region in REGIONS))
    await asyncio.gather(*(cache.render(kind) for kind in ReportKind))


async def drain_workers(queue, worker_count):
    await asyncio.gather(*(drain(queue) for _ in range(worker_count)))


async def summarize_documents(summarizer, documents):
    return await asyncio.gather(*(summarizer.summarize(document) for document in documents))


async def export_recent(exporter, store, limit: int):
    records = await store.list_records(50)
    await asyncio.gather(*(exporter.export(record) for record in records))
    paged = await store.list_records(size=PAGE_SIZE)
    await asyncio.gather(*(exporter.export(record) for record in paged))
    asked = await store.list_records(limit=min(limit, PAGE_SIZE))
    await asyncio.gather(*(exporter.export(record) for record in asked))


async def export_first(exporter, store):
    records = await store.list_records()
    await asyncio.gather(*(exporter.export(record) for record in records[:10]))


async def export_sample_files(reader, jobs, job_id):
    job = await jobs.get(job_id)
    await asyncio.gather(*(reader.read(file) for file in job.files))


async def rerank(rankers, groups):
    current = groups
    for ranker in rankers:
        current = await ranker.rank(current)
    await asyncio.gather(*(publish(group) for group in current))


async def claim_items(batch_id):
    return []


async def dispatch_claimed(dispatcher, batch_id):
    await asyncio.gather(*(dispatcher.dispatch(item) for item in await claim_items(batch_id)))


class BatchConsumer:
    async def fetch_batch(self, subscription):
        return await subscription.fetch(batch=10)

    async def run(self, subscription):
        messages = await self.fetch_batch(subscription)
        await asyncio.gather(*(self.process(message) for message in messages))


async def gather_all(*awaitables):
    await asyncio.gather(*(asyncio.ensure_future(awaitable) for awaitable in awaitables))
"""
FAN_OUT = """import asyncio


async def fetch_invoices(client):
    invoice_ids = await client.list_invoice_ids()
    return await asyncio.gather(*(client.fetch_invoice(invoice_id) for invoice_id in invoice_ids))
"""


def test_fan_outs_over_external_loads_are_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": UNBOUNDED_FAN_OUTS})
    assert rule_findings(report, RULE_ID) == UNBOUNDED_LINES


def test_collections_that_are_not_external_loads_are_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": BOUNDED_FAN_OUTS})
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [("tests/test_invoices.py", FAN_OUT), ("invoices.py", f"from temporalio import workflow\n{FAN_OUT}")],
)
def test_tests_and_durable_workflows_are_exempt(run_pristine: RunPristine, path: str, source: str) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []


def test_fan_out_in_an_application_module_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": FAN_OUT})
    assert rule_findings(report, RULE_ID) == [(6, "warning")]
