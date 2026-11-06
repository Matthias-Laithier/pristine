from pathlib import Path

import pristine.checks.registry
from tests.conftest import RunPristine, rule_findings

PYTHON_WRITES = (
    "from collections import defaultdict\n"
    "PENDING = []\n"
    "COUNTS = defaultdict(int)\n"
    "STATUSES = ('paid',)\n"
    "def queue(invoice):\n"
    "    PENDING.append(invoice)\n"
    "    COUNTS[invoice] += 1\n"
    "    del COUNTS['old']\n"
    "    STATUSES.count('paid')\n"
    "def bump():\n"
    "    global TOTAL\n"
    "def shadow(PENDING):\n"
    "    PENDING.append(1)\n"
    "def rebuild():\n"
    "    COUNTS = {}\n"
    "    COUNTS['a'] = 1\n"
)
PYTHON_OWNED = (
    "import pytest\n"
    "_HANDLERS = {}\n"
    "HOOKS = []\n"
    "ROWS = []\n"
    "def handles(event_type):\n"
    "    def register(handler):\n"
    "        HOOKS.append(handler)\n"
    "        _HANDLERS[event_type] = handler\n"
    "    return register\n"
    "@pytest.fixture\n"
    "def rows():\n"
    "    ROWS.clear()\n"
    "ROWS.append(0)\n"
)
JS_WRITES = (
    "let count = 0;\n"
    "export const pending: string[] = [];\n"
    "const index = new Map();\n"
    "const state = { open: false };\n"
    "const LIMIT = 3;\n"
    "export function bump(invoice) {\n"
    "  count += 1;\n"
    "  pending.push(invoice);\n"
    "  index.set(invoice, 1);\n"
    "  state.open = true;\n"
    "  pending.map((each) => each);\n"
    "}\n"
    "const local = (count) => { count = 2; const pending = []; pending.push(1); };\n"
    "count = LIMIT;\n"
)
JS_OWNED = (
    "const formats = new Map();\n"
    "const listeners = new Set();\n"
    "let english;\n"
    "let seen = [];\n"
    "export function formatFor(locale) {\n"
    "  const known = formats.get(locale);\n"
    "  formats.set(locale, known ?? locale);\n"
    "  english ??= locale;\n"
    "}\n"
    "export const subscribe = (listener) => { listeners.add(listener); };\n"
    "beforeEach(() => { seen = []; });\n"
)


def test_python_writes_to_module_state_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": PYTHON_WRITES})
    assert rule_findings(report, "CR-7") == [(6, "error"), (7, "error"), (8, "error"), (11, "error")]


def test_python_registries_fixtures_and_module_setup_are_allowed(run_pristine: RunPristine) -> None:
    registry_source = Path(pristine.checks.registry.__file__).read_text()
    _, report = run_pristine({"handlers.py": PYTHON_OWNED, "registry.py": registry_source})
    assert rule_findings(report, "CR-7") == []


def test_js_writes_to_module_state_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.ts": JS_WRITES})
    assert rule_findings(report, "CR-7") == [(7, "error"), (8, "error"), (9, "error"), (10, "error")]


def test_js_memo_caches_listeners_and_test_hooks_are_allowed(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"formats.js": JS_OWNED})
    assert rule_findings(report, "CR-7") == []
