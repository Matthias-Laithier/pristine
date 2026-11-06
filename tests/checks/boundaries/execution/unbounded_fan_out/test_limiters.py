from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-14"
LIMITED_FAN_OUTS = """import asyncio

import anyio

MAX_CONCURRENT_FETCHES = 8
FETCH_LIMIT = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)


async def fetch_invoices(client):
    invoice_ids = await client.list_invoice_ids()
    limit = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch(invoice_id):
        async with limit:
            return await client.fetch_invoice(invoice_id)

    return await asyncio.gather(*(fetch(invoice_id) for invoice_id in invoice_ids))


async def fetch_within(limiter, client, invoice_id):
    async with limiter:
        return await client.fetch_invoice(invoice_id)


async def fetch_passing_the_limit(client):
    invoice_ids = await client.list_invoice_ids()
    limiter = anyio.CapacityLimiter(MAX_CONCURRENT_FETCHES)
    return await asyncio.gather(*(fetch_within(limiter, client, invoice_id) for invoice_id in invoice_ids))


async def fetch_module_limited(client, invoice_id):
    async with FETCH_LIMIT:
        return await client.fetch_invoice(invoice_id)


async def fetch_all(client):
    invoice_ids = await client.list_invoice_ids()
    return await asyncio.gather(*(fetch_module_limited(client, invoice_id) for invoice_id in invoice_ids))


class InvoiceFetcher:
    def __init__(self, client):
        self.client = client
        self.slots = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch(self, invoice_id):
        async with self.slots:
            return await self.client.fetch_invoice(invoice_id)

    async def fetch_all(self):
        invoice_ids = await self.client.list_invoice_ids()
        async with asyncio.TaskGroup() as task_group:
            for invoice_id in invoice_ids:
                task_group.create_task(self.fetch(invoice_id))
"""
UNRELATED_LIMIT = """import asyncio

# Each batch is limited, chunked, and paged upstream.
CHUNK_LIMIT = asyncio.Semaphore(4)


async def fetch_invoice_batch_page(client):
    invoice_ids = await client.list_invoice_ids()
    return await asyncio.gather(*(client.fetch_invoice(invoice_id) for invoice_id in invoice_ids))
"""


def test_work_that_holds_a_semaphore_or_limiter_is_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": LIMITED_FAN_OUTS})
    assert rule_findings(report, RULE_ID) == []


def test_a_limiter_the_work_never_holds_and_bounding_words_change_nothing(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": UNRELATED_LIMIT})
    assert rule_findings(report, RULE_ID) == [(9, "warning")]
