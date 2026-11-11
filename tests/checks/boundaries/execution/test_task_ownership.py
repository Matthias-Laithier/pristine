from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-5"
TASKS = """import asyncio
import asyncio as aio
from asyncio import create_task, ensure_future


async def refresh_rates(rate_source, loop):
    asyncio.create_task(rate_source.fetch())
    aio.ensure_future(rate_source.fetch())
    create_task(rate_source.fetch())
    ensure_future(rate_source.fetch())
    loop.create_task(rate_source.fetch())
    asyncio.get_running_loop().create_task(rate_source.fetch())
    task = asyncio.create_task(rate_source.fetch())
    pending = [asyncio.create_task(rate_source.fetch())]
    pending.append(asyncio.create_task(rate_source.fetch()))
    await asyncio.create_task(rate_source.fetch())
    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(rate_source.fetch())
    scheduler.create_task(rate_source.fetch())
    await asyncio.gather(task, *pending)
    return asyncio.create_task(rate_source.fetch())
"""
CANCELLATION = """import asyncio
from asyncio import CancelledError


async def refresh_rates(rate_source):
    try:
        await rate_source.fetch()
    except asyncio.CancelledError:
        rate_source.close()
    try:
        async for rate in rate_source.stream():
            rate_source.store(rate)
    except (ValueError, CancelledError):
        rate_source.close()
    try:
        await rate_source.fetch()
    except BaseException:
        rate_source.close()
    try:
        await rate_source.fetch()
    except:
        rate_source.close()
    try:
        await rate_source.fetch()
    except asyncio.CancelledError:
        rate_source.close()
        raise
    try:
        await rate_source.fetch()
    except BaseException as error:
        raise RefreshFailed() from error
    try:
        await rate_source.fetch()
    except asyncio.CancelledError as error:
        cancelled = error
    try:
        await rate_source.fetch()
    except BaseException as error:
        failures.append(error)
    try:
        await rate_source.fetch()
    except Exception:
        rate_source.close()
    try:
        rate_source.pending.result()
    except asyncio.CancelledError:
        rate_source.close()
    raise cancelled


async def stop_refresh(refresh_task, rate_source):
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
    try:
        await rate_source.fetch()
    except BaseException:
        try:
            await rate_source.close()
        except BaseException:
            rate_source.abort()
        raise


def close_rates(rate_source):
    try:
        rate_source.close()
    except (BaseException, asyncio.CancelledError):
        rate_source.abort()
"""


def test_dropped_tasks_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"rates.py": TASKS})
    assert rule_findings(report, CHECK_ID) == [(line, "error") for line in range(7, 13)]


def test_swallowed_cancellations_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"rates.py": CANCELLATION})
    assert rule_findings(report, CHECK_ID) == [(8, "error"), (13, "error"), (17, "error"), (21, "error")]


def test_swallowed_cancellation_is_not_a_failure_swallow(run_pristine: RunPristine) -> None:
    source = "import asyncio\n\n\nasync def refresh(source):\n    try:\n        await source.fetch()\n"
    _, report = run_pristine({"rates.py": source + "    except asyncio.CancelledError:\n        pass\n"})
    assert rule_findings(report, CHECK_ID) == [(7, "error")]
    assert rule_findings(report, "SAFE-4") == []


def test_unimported_names_are_not_resolved(run_pristine: RunPristine) -> None:
    source = "async def refresh(asyncio):\n    asyncio.create_task(job())\n    try:\n        await job()\n"
    _, report = run_pristine({"rates.py": source + "    except asyncio.CancelledError:\n        pass\n"})
    assert rule_findings(report, CHECK_ID) == []


def test_formatted_or_logged_cancellation_is_still_swallowed(run_pristine: RunPristine) -> None:
    source = """import asyncio


async def publish_rates(rate_source, setup_error):
    try:
        await rate_source.publish()
    except asyncio.CancelledError as error:
        logger.warning(f"publish stopped: {error!r}", reason=str(error), exc_info=error)
    try:
        await rate_source.publish()
    except asyncio.CancelledError:
        return
    except BaseException as error:
        failures.append(error)
    try:
        await rate_source.close()
    except BaseException as cleanup_error:
        setup_error.add_note(f"cleanup failed: {cleanup_error!r}")
"""
    _, report = run_pristine({"rates.py": source})
    assert rule_findings(report, CHECK_ID) == [(7, "error"), (11, "error")]
