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
    "HANDLERS = {}\n"
    "HOOKS = []\n"
    "ROWS = []\n"
    "RATES = {}\n"
    "def handles(event_type):\n"
    "    def register(handler):\n"
    "        HOOKS.append(handler)\n"
    "        HANDLERS[event_type] = handler\n"
    "        return handler\n"
    "    return register\n"
    "def rate_for(currency):\n"
    "    if currency not in RATES:\n"
    "        RATES[currency] = fetch_rate(currency)\n"
    "    return RATES[currency]\n"
    "def load_rates():\n"
    "    if not RATES:\n"
    "        RATES.update(fetch_all_rates())\n"
    "def reset_rates():\n"
    "    RATES.clear()\n"
    "@pytest.fixture\n"
    "def rows():\n"
    "    ROWS.clear()\n"
    "ROWS.append(0)\n"
)
PYTHON_NAMED_LIKE_OWNED = (
    "from metrics import Counter\n"
    "_PENDING = []\n"
    "_invoice_cache = {}\n"
    "SENT = Counter(name='sent')\n"
    "def register_invoice(invoice):\n"
    "    _PENDING.append(invoice)\n"
    "    _invoice_cache[invoice.id] = invoice\n"
    "    SENT.add(1)\n"
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
    "export const subscribe = (listener) => {\n"
    "  listeners.add(listener);\n"
    "  return () => listeners.delete(listener);\n"
    "};\n"
    "beforeEach(() => { seen = []; });\n"
    "let highlighter;\n"
    "export function loadHighlighter() {\n"
    "  if (highlighter === undefined) { highlighter = createHighlighter(); }\n"
    "  return highlighter;\n"
    "}\n"
)
JS_FLAGS = (
    "let reconnecting = false;\n"
    "let context = null;\n"
    "export function reconnect() {\n"
    "  if (reconnecting) { return; }\n"
    "  reconnecting = true;\n"
    "  retry();\n"
    "  reconnecting = false;\n"
    "}\n"
    "export function finishReconnect() {\n"
    "  reconnecting = false;\n"
    "}\n"
    "export function canvasContext() {\n"
    "  if (context) return context;\n"
    "  context = createContext();\n"
    "  return context;\n"
    "}\n"
)


def test_python_writes_to_module_state_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": PYTHON_WRITES})
    assert rule_findings(report, "SAFE-10") == [(6, "error"), (7, "error"), (8, "error"), (11, "error")]


def test_python_memos_fixtures_and_module_setup_are_allowed_and_registrations_are_errors(
    run_pristine: RunPristine,
) -> None:
    _, report = run_pristine({"handlers.py": PYTHON_OWNED})
    findings = [finding for finding in report["findings"] if finding["check_id"] == "SAFE-10"]
    assert [finding["line"] for finding in findings] == [8, 9]
    assert all(
        "write the registry as a dict literal in its owning module" in finding["message"] for finding in findings
    )


def test_private_cache_and_registration_names_alone_do_not_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": PYTHON_NAMED_LIKE_OWNED})
    assert rule_findings(report, "SAFE-10") == [(6, "error"), (7, "error")]


def test_js_writes_to_module_state_are_errors(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.ts": JS_WRITES})
    assert rule_findings(report, "SAFE-10") == [(7, "error"), (8, "error"), (9, "error"), (10, "error")]


def test_js_lazy_initialization_is_allowed_and_a_later_reset_is_an_error(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"connection.js": JS_FLAGS})
    assert rule_findings(report, "SAFE-10") == [(7, "error"), (10, "error")]


def test_js_memo_caches_listeners_and_test_hooks_are_allowed(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"formats.js": JS_OWNED})
    assert rule_findings(report, "SAFE-10") == []
