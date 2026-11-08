import selectors
import sys

from pytest import MonkeyPatch

from pristine.reports.outcomes import Checked
from pristine.services import worker_pool
from pristine.services.isolated_inspection import worker_outcomes
from tests.services.worker_commands import CHECKING_WORKER


def test_finishing_all_work_does_not_poll_an_empty_selector(monkeypatch: MonkeyPatch) -> None:
    default_selector = selectors.DefaultSelector
    empty_poll_timeouts: list[float | None] = []

    def recording_selector() -> selectors.DefaultSelector:
        selector = default_selector()
        read_ready = selector.select

        def select(timeout: float | None = None) -> list[tuple[selectors.SelectorKey, int]]:
            if selector.get_map():
                return read_ready(timeout)
            empty_poll_timeouts.append(timeout)
            return []

        monkeypatch.setattr(selector, "select", select)
        return selector

    monkeypatch.setattr(worker_pool.selectors, "DefaultSelector", recording_selector)
    command = (sys.executable, "-c", CHECKING_WORKER)

    with worker_outcomes(["invoice.py"], jobs=1, command=command) as completed:
        result = dict(completed)

    assert result == {"invoice.py": Checked([])}
    assert empty_poll_timeouts == []
