import pytest

from tests.conftest import RunPristine, rule_findings

FAN_OUT = (
    "import asyncio\n\nfrom archive import list_documents\n\n\nasync def summarize(summarizer):\n"
    "    documents = await list_documents()\n"
    "    return await asyncio.gather(*(summarizer.summarize(document) for document in documents))\n"
)
SCRIPT_FAN_OUT = (
    "import { loadItems } from './services/items';\nasync function refresh() {\n"
    "  const items = await loadItems();\n  return Promise.all(items.map(async item => await save(item)));\n}\n"
)
CANCELLATION = "async def refresh(source):\n    try:\n        await source.fetch()\n    except BaseException:\n        source.close()\n"
LIVE_CLIENT = "import os\nimport cohere as c\n\nc.Client(api_key=os.environ['K']).chat.send()\n"


@pytest.mark.parametrize(
    ("path", "source", "check_id", "expected"),
    [
        pytest.param(
            "tests/test_wait.py",
            "from time import sleep as pause\n\n\ndef test_wait():\n    pause(1)\n",
            "TEST-3",
            [(5, "warning")],
            id="TEST-3-sleep-only-named-by-its-aliased-import",
        ),
        pytest.param(
            "src/a.test.ts",
            "test('x', () => { setTimeout(done, 5); });\n",
            "TEST-3",
            [(1, "warning")],
            id="TEST-3-script-timer-names-setTimeout",
        ),
        pytest.param("src/a.py", "try:\n    run()\nexcept:\n    pass\n", "SAFE-4", [(3, "error")], id="SAFE-4-except"),
        pytest.param("src/a.ts", "try { run(); } catch {}\n", "SAFE-4", [(1, "warning")], id="SAFE-4-catch"),
        pytest.param("src/a.py", CANCELLATION, "SAFE-5", [(4, "error")], id="SAFE-5-cancellation-needs-async"),
        pytest.param(
            "src/a.ts",
            "import fetchIt from 'node-fetch';\nfetchIt(url);\n",
            "SAFE-5",
            [(2, "error")],
            id="SAFE-5-dropped-operation-names-its-module",
        ),
        pytest.param(
            "src/a.py", "client.chat(model='gpt-4o')\n", "SAFE-13", [(1, "warning")], id="SAFE-13-model-keyword"
        ),
        pytest.param(
            "src/a.ts",
            "client.create({ model: 'gpt-4o' });\n",
            "SAFE-13",
            [(1, "warning")],
            id="SAFE-13-script-model-key",
        ),
        pytest.param(
            "app/cache.py",
            "import redis as kv\n\nkv.Redis()\n",
            "STR-6",
            [(1, "warning")],
            id="STR-6-aliased-client-still-names-its-package",
        ),
        pytest.param(
            "app/db.ts",
            "import pg from 'pg';\npg.connect();\n",
            "STR-6",
            [(1, "warning")],
            id="STR-6-script-client-names-its-package",
        ),
        pytest.param(
            "tests/test_live.py",
            LIVE_CLIENT,
            "TEST-5",
            [(4, "warning")],
            id="TEST-5-aliased-model-sdk-names-its-package",
        ),
        pytest.param(
            "src/a.py",
            "from subprocess import run as sh\n\nsh(['ls'])\n",
            "SAFE-3",
            [(3, "error")],
            id="SAFE-3-aliased-call-names-its-module",
        ),
        pytest.param("src/a.ts", "fetch(url);\n", "SAFE-3", [(1, "warning")], id="SAFE-3-script-fetch"),
        pytest.param("src/a.py", "LOG.info(f'x {y}')\n", "SAFE-9", [(1, "warning")], id="SAFE-9-upper-case-logger"),
        pytest.param("src/a.ts", "console.info(`x ${y}`);\n", "SAFE-9", [(1, "warning")], id="SAFE-9-console-logger"),
        pytest.param(
            "src/a.py",
            "from typing import cast as narrow\n\nnarrow(int, x)\n",
            "SAFE-14",
            [(3, "warning")],
            id="SAFE-14-cast-only-named-by-its-aliased-import",
        ),
        pytest.param(
            "src/a.py",
            "from os import getenv\n\n\ndef region():\n    return getenv('REGION')\n",
            "SAFE-1",
            [(5, "warning")],
            id="SAFE-1-getenv",
        ),
        pytest.param(
            "src/billing.ts",
            "export function region() {\n  return process.env.REGION;\n}\n",
            "SAFE-1",
            [(2, "warning")],
            id="SAFE-1-script-process-env",
        ),
        pytest.param("src/a.py", FAN_OUT, "SAFE-8", [(8, "warning")], id="SAFE-8-gather"),
        pytest.param("src/a.ts", SCRIPT_FAN_OUT, "SAFE-8", [(4, "warning")], id="SAFE-8-script-promise-all"),
        pytest.param(
            "src/a.py",
            "from datetime import datetime\n\nstamp = datetime.utcnow()\n",
            "SAFE-15",
            [(3, "error")],
            id="SAFE-15-datetime",
        ),
        pytest.param(
            "src/a.py",
            "import time\n\n\nasync def wait():\n    time.sleep(1)\n",
            "SAFE-7",
            [(5, "error")],
            id="SAFE-7-async",
        ),
        pytest.param(
            "src/a.ts",
            "import { readFileSync } from 'fs';\nasync function load() {\n  return readFileSync('a');\n}\n",
            "SAFE-7",
            [(3, "error")],
            id="SAFE-7-script-async",
        ),
        pytest.param(
            "src/a.py",
            'def find(cursor, name):\n    cursor.execute(f"""\n  select * from t where n = {name}""")\n',
            "SAFE-6",
            [(2, "error")],
            id="SAFE-6-sql-keyword-after-quote-and-whitespace",
        ),
        pytest.param(
            "src/a.py",
            "from subprocess import getstatusoutput as sh\n\nsh(command)\n",
            "SAFE-6",
            [(3, "error")],
            id="SAFE-6-aliased-shell-names-output",
        ),
        pytest.param("src/a.ts", "node.innerHTML = html;\n", "SAFE-6", [(1, "error")], id="SAFE-6-script-markup"),
        pytest.param("src/a.ts", "eval(code);\n", "SAFE-6", [(1, "error")], id="SAFE-6-script-eval"),
        pytest.param(
            "src/mod.py", "__all__ = ['missing']\n", "DEP-4", [(1, "error")], id="DEP-4-export-list-outside-init"
        ),
        pytest.param(
            "src/pkg/__init__.py",
            "from .delivery import send_invoice\n",
            "DEP-4",
            [(1, "warning")],
            id="DEP-4-package-init-without-export-list",
        ),
        pytest.param(
            "src/index.ts", "export * from './delivery';\n", "DEP-4", [(1, "warning")], id="DEP-4-script-index"
        ),
    ],
)
def test_text_prefilters_keep_minimal_findings(
    run_pristine: RunPristine, path: str, source: str, check_id: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, check_id) == expected
