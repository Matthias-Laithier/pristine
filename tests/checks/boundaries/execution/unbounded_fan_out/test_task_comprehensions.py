import pytest

from tests.conftest import RunPristine, rule_findings

SOURCE = """import asyncio


async def summarize_batch(document_store, summarizer):
    documents = await document_store.list_documents(timeout=3)
    concurrency_limit = asyncio.Semaphore(8)

    async def summarize_within_limit(document):
        async with concurrency_limit:
            return await summarizer.summarize(document)

    async with asyncio.TaskGroup() as task_group:
        tasks = [task_group.create_task({coroutine}(document)) for document in documents]
    return [task.result() for task in tasks]
"""


@pytest.mark.parametrize(
    ("coroutine", "expected"),
    [("summarizer.summarize", [(13, "warning")]), ("summarize_within_limit", [])],
)
def test_task_comprehensions_require_a_concurrency_limit(
    run_pristine: RunPristine, coroutine: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"summaries.py": SOURCE.format(coroutine=coroutine)})
    assert rule_findings(report, "SAFE-8") == expected
