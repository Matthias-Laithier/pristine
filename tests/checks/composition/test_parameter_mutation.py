import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-11"
FLAGGED = {
    "item write": "def mark_paid(order, paid_at):\n    order['paid_at'] = paid_at\n",
    "augmented item": "def apply_discount(order, cents):\n    order['total'] -= cents\n",
    "nested item": "def tag(spec, name):\n    spec['tags'][name] = True\n",
    "item delete": "def drop(order, key):\n    del order[key]\n",
    "collection method": "def queue(pending: list[str], name: str) -> None:\n    pending.append(name)\n",
    "optional collection": "def queue(pending: dict[str, int] | None, name):\n    pending.pop(name)\n",
}
KEPT = {
    "private": "def _mark_paid(order, paid_at):\n    order['paid_at'] = paid_at\n",
    "test function": "def test_mark(order):\n    order['paid'] = True\n",
    "decorated": "@pytest.fixture\ndef order(order):\n    order['paid'] = True\n",
    "method": "class Orders:\n    def mark(self, order):\n        order['paid'] = True\n",
    "nested function": "def build():\n    def mark(order):\n        order['paid'] = True\n",
    "rebound": "def mark(order):\n    order = dict(order)\n    order['paid'] = True\n    return order\n",
    "loop rebound": "def mark(orders):\n    for orders in batches:\n        orders['paid'] = True\n",
    "array kernel": "def cache(blocks, slots, values):\n    blocks[slots // 16, :, slots % 16] = values\n",
    "attribute write": "def mark(order):\n    order.paid = True\n",
    "untyped method": "def queue(pending, name):\n    pending.append(name)\n",
    "service method": "def save(session: Session, row):\n    session.add(row)\n",
    "local": "def build(name):\n    pending = {}\n    pending[name] = 1\n    return pending\n",
    "callback": "def stamp(headers):\n    headers['at'] = 1\n\n\nsignal.connect(stamp)\n",
}


@pytest.mark.parametrize("source", FLAGGED.values(), ids=FLAGGED.keys())
def test_parameter_mutation_is_a_warning(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"orders.py": source})
    assert rule_findings(report, CHECK_ID) == [(2, "warning")]


@pytest.mark.parametrize("source", KEPT.values(), ids=KEPT.keys())
def test_mutation_with_an_owner_is_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"orders.py": source})
    assert rule_findings(report, CHECK_ID) == []


def test_each_mutated_parameter_is_reported_once(run_pristine: RunPristine) -> None:
    source = "def merge(target, issues: list):\n    target['a'] = 1\n    target['b'] = 2\n    issues.append(3)\n"
    _, report = run_pristine({"orders.py": source})
    assert rule_findings(report, CHECK_ID) == [(2, "warning"), (4, "warning")]


def test_test_files_are_kept(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/helpers.py": "def mark(order):\n    order['paid'] = True\n"})
    assert rule_findings(report, CHECK_ID) == []
