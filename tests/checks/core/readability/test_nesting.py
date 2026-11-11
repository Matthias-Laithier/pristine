import pytest

from tests.conftest import RunPristine, rule_findings

TWO_LEVELS = "def ship(orders):\n    for order in orders:\n        if order.paid:\n            send(order)\n"
THREE_LEVELS = (
    "def ship(orders):\n    for order in orders:\n        if order.paid:\n"
    "            with lock(order):\n                send(order)\n"
)
FOUR_LEVELS = (
    "def ship(orders):\n    for order in orders:\n        if order.paid:\n            with lock(order):\n"
    "                while order.pending:\n                    send(order)\n"
)
ELSE_IF_CHAIN = (
    "function route(order) {\n  for (const line of order.lines) {\n    if (line.a) { send(line); }\n"
    "    else if (line.b) { hold(line); }\n    else if (line.c) { drop(line); }\n  }\n}\n"
)
COMPREHENSION_LEVEL = (
    "def ship(batches):\n    for batch in batches:\n        if batch.ready:\n"
    "            send([order for order in batch.orders if order.paid])\n"
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [(TWO_LEVELS, []), (THREE_LEVELS, [(4, "warning")]), (FOUR_LEVELS, [(5, "error")])],
)
def test_nesting_limits(run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"ship.py": source})
    assert rule_findings(report, "STR-3") == expected


def test_else_if_adds_no_level(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"route.js": ELSE_IF_CHAIN})
    assert rule_findings(report, "STR-3") == []


def test_comprehension_adds_one_level(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"ship.py": COMPREHENSION_LEVEL})
    assert rule_findings(report, "STR-3") == [(4, "warning")]


def test_function_bound_to_a_name_opens_its_own_scope(run_pristine: RunPristine) -> None:
    source = (
        "export const useOrders = (orders) => {\n  useEffect(() => {\n    for (const order of orders) {\n"
        "      if (order.paid) { send(order); }\n    }\n  });\n};\n"
    )
    _, report = run_pristine({"use-orders.ts": source})
    assert rule_findings(report, "STR-3") == [(4, "warning")]


def test_test_framework_callbacks_add_no_level(run_pristine: RunPristine) -> None:
    source = (
        'describe("invoice", () => {\n  it.each(cases)("sums %s", (lines) => {\n'
        "    for (const line of lines) {\n      if (line.paid) {\n        expect(line).toBeTruthy();\n"
        "      }\n    }\n  });\n});\n"
        'register("invoice", () => {\n  for (const line of lines) {\n    if (line.paid) {\n'
        "      while (line.pending) { settle(line); }\n    }\n  }\n});\n"
    )
    _, report = run_pristine({"invoice.test.ts": source})
    assert rule_findings(report, "STR-3") == [(13, "error")]
