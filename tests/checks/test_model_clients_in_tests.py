from tests.conftest import RunPristine, rule_findings

RULE_ID = "TST-8"
PYTHON_SOURCE = """import os
from mistralai import Mistral
import openai

live_client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
live_client.chat.complete(model="mistral-small-latest", messages=messages)
"""
SCRIPT_SOURCE = """import type { Mistral } from "@mistralai/mistralai";
import Anthropic from "@anthropic-ai/sdk";
const liveClient = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
await liveClient.messages.create(request);
"""


def test_tests_calling_real_model_clients_are_warnings(run_pristine: RunPristine) -> None:
    files = {"tests/test_summary.py": PYTHON_SOURCE, "src/summary.test.ts": SCRIPT_SOURCE}
    _, report = run_pristine(files)
    assert rule_findings(report, RULE_ID) == [(2, "warning"), (2, "warning")]


def test_evals_production_code_fakes_and_non_client_imports_are_exempt(run_pristine: RunPristine) -> None:
    files = {
        "evals/tests/test_summary.py": PYTHON_SOURCE,
        "services/summary.py": PYTHON_SOURCE,
        "tests/test_recorded.py": 'from mistralai import Mistral\nclient = Mistral(api_key="recorded")\nclient.chat.complete()\n',
        "tests/test_files.py": 'import os\nfrom mistralai import Mistral\nMistral(api_key=os.environ["MISTRAL_API_KEY"]).files.list()\n',
        "tests/test_offline.py": 'import os\nimport openai\nos.environ["OPENAI_API_KEY"] = "offline"\nopenai.chat.completions.create()\n',
        "tests/test_errors.py": 'import os\nfrom anthropic.types import Message\nos.getenv("ANTHROPIC_API_KEY")\nclient.messages.create()\n',
        "src/types.test.ts": 'import type { Mistral } from "@mistralai/mistralai";\nprocess.env.MISTRAL_API_KEY;\nclient.chat.complete();\n',
    }
    _, report = run_pristine(files)
    assert rule_findings(report, RULE_ID) == []


def test_conftest_counts_and_test_support_files_are_exempt(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/recorded/record.py": PYTHON_SOURCE, "tests/conftest.py": PYTHON_SOURCE})
    assert rule_findings(report, RULE_ID) == [(2, "warning")]
