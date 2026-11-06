from tests.conftest import RunPristine, rule_findings

RULE_ID = "CR-22"
SOURCE = """import datetime as dt
from datetime import UTC, date, datetime

datetime.utcnow()
datetime.utcfromtimestamp(created_at)
datetime.now()
datetime.now(tz=None)
datetime.fromtimestamp(created_at)
datetime.today()
dt.datetime.now()
datetime.now(UTC)
datetime.now(tz=UTC)
datetime.fromtimestamp(created_at, UTC)
datetime.fromtimestamp(created_at, tz=UTC)
date.today()
dt.date.today()
datetime.now().astimezone()
(datetime.now() - timedelta(days=1)).date()
int(datetime.fromtimestamp(created_at).timestamp())
datetime.now().strftime("%Y%m%d")
datetime.utcnow().astimezone()
datetime.now().isoformat()


def is_halloween():
    now = datetime.now()
    return now.month == 10 and now.day == 31


def record_order(order):
    placed_at = datetime.now()
    order.placed_at = placed_at
    return placed_at.month
"""


def test_naive_datetimes_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"clock.py": SOURCE})
    assert rule_findings(report, RULE_ID) == [(line, "error") for line in [*range(4, 11), 21, 22, 31]]


def test_unimported_datetime_is_not_resolved(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"clock.py": "datetime.now()\npendulum.now()\n"})
    assert rule_findings(report, RULE_ID) == []
