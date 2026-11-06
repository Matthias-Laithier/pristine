import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-14"
UNBOUNDED_FAN_OUTS = """import asyncio


async def summarize_documents(summarizer, documents):
    return await asyncio.gather(*(summarizer.summarize(document) for document in documents))


async def delete_blobs(storage, blobs_list):
    await asyncio.gather(*[storage.delete(blob.name) for blob in blobs_list])


async def fetch_invoices(client, invoice_ids):
    return await asyncio.gather(*map(client.fetch_invoice, invoice_ids))


async def notify_members(notifier, team):
    async with asyncio.TaskGroup() as task_group:
        for member in team.members:
            task_group.create_task(notifier.notify(member))
"""
BOUNDED_FAN_OUTS = """import asyncio

from billing import ReportKind

REGIONS = ("eu", "us")


async def warm_regions(cache):
    await asyncio.gather(*(cache.warm(region) for region in ("eu", "us", "asia")))
    await asyncio.gather(*(cache.warm(region) for region in REGIONS))
    await asyncio.gather(*(cache.render(kind) for kind in ReportKind))


async def drain_workers(queue, worker_count):
    await asyncio.gather(*(drain(queue) for _ in range(worker_count)))


async def close_connections(connections):
    await asyncio.gather(*(connection.close() for connection in connections))


async def await_pending(tasks):
    await asyncio.gather(*(task for task in tasks))


async def check_probes(probes):
    await asyncio.gather(*(run_probe(probe) for probe in probes))


async def export_page(exporter, page):
    await asyncio.gather(*(exporter.export(record) for record in page.records))


async def export_recent(exporter, store):
    records = await store.list_records(limit=50)
    await asyncio.gather(*(exporter.export(record) for record in records))
"""
SEMAPHORE_MODULE = """import asyncio

MAX_CONCURRENT_FETCHES = 8


async def fetch_invoices(client, invoice_ids):
    limit = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch(invoice_id):
        async with limit:
            return await client.fetch_invoice(invoice_id)

    return await asyncio.gather(*(fetch(invoice_id) for invoice_id in invoice_ids))
"""
FAN_OUT = """import asyncio


async def fetch_invoices(client, invoice_ids):
    return await asyncio.gather(*(client.fetch_invoice(invoice_id) for invoice_id in invoice_ids))
"""


def test_fan_outs_over_data_collections_are_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": UNBOUNDED_FAN_OUTS})
    assert rule_findings(report, RULE_ID) == [(5, "warning"), (9, "warning"), (13, "warning"), (19, "warning")]


def test_fixed_component_and_bounded_collections_are_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": BOUNDED_FAN_OUTS})
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("invoices.py", SEMAPHORE_MODULE),
        ("tests/test_invoices.py", FAN_OUT),
        ("invoices.py", f"from temporalio import workflow\n{FAN_OUT}"),
    ],
)
def test_bounded_modules_tests_and_durable_workflows_are_exempt(
    run_pristine: RunPristine, path: str, source: str
) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []


def test_fan_out_in_an_application_module_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": FAN_OUT})
    assert rule_findings(report, RULE_ID) == [(5, "warning")]
