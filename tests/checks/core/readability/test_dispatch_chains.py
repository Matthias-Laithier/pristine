import pytest

from tests.conftest import RunPristine, rule_findings

PYTHON_CHAIN = (
    "def route(event):\n    if event.type == 'paid':\n        settle(event)\n"
    "    elif event.type is Kind.FAILED:\n        retry(event)\n    elif event.type == 3 or event.type == -4:\n"
    "        reopen(event)\n"
)
PYTHON_TWO_BRANCHES = "def route(event):\n    if event.type == 'paid':\n        settle(event)\n    elif event.type == 'failed':\n        retry(event)\n"
PYTHON_GUARDS = (
    "def route(event):\n    if event.type == 'paid':\n        return settle(event)\n"
    "    if event.type == 'failed':\n        return retry(event)\n    if event.type == 'refunded':\n        return reopen(event)\n"
)
PYTHON_MATCH = (
    "def route(event):\n    match event.type:\n        case 'paid':\n            settle(event)\n"
    "        case Kind.FAILED | Kind.LOST:\n            retry(event)\n        case 3:\n            reopen(event)\n"
)
PYTHON_TWO_CASE_MATCH = (
    "def route(event):\n    match event.type:\n        case 'paid':\n            settle(event)\n"
    "        case 'failed':\n            retry(event)\n        case other if other.startswith('x'):\n            drop(event)\n"
    "        case _:\n            reject(event)\n"
)
ERROR = [(1, "error")]
WARNING = [(1, "warning")]


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("route.py", PYTHON_CHAIN, [(2, "error")]),
        ("route.py", PYTHON_TWO_BRANCHES, []),
        ("route.py", PYTHON_GUARDS, []),
        ("route.js", "if (k === 'a') f(); else if (k == Kind.B) g(); else if ((k === 1 || k === 2)) h();", ERROR),
        ("route.js", "if (k === 'a') f(); else if (j === 'b') g(); else if (k === `c${x}`) h();", []),
        (
            "route.ts",
            "if (typeof k === 'string') f(); else if (typeof k === 'number') g(); else if (typeof k === 'object') h();",
            [],
        ),
    ],
)
def test_if_else_if_chains(run_pristine: RunPristine, name: str, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, "CR-14") == expected


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("route.py", PYTHON_MATCH, [(2, "warning")]),
        ("route.py", PYTHON_TWO_CASE_MATCH, []),
        ("route.js", "switch (k) { case 'a': a(); break; case Kind.B: case 3: b(); break; case 4: c(); }", WARNING),
        ("route.js", "switch (k) { case 'a': case 'b': case 'c': return true; default: return false; }", []),
    ],
)
def test_switch_and_match(run_pristine: RunPristine, name: str, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, "CR-14") == expected
