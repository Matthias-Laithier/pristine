import pytest

from tests.conftest import RunPristine, rule_findings

HTTPX_CLIENT = "import os\nimport httpx\n\nCLIENT = httpx.AsyncClient()\n"
HTTPX_ERRORS_ONLY = "import httpx\n\nRETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)\n"
TYPE_CHECKING_IMPORT = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import boto3\n"
MISTRAL_CLIENT = "from mistralai.workflows import workflow\nfrom mistralai.client import Mistral\n"
MISTRAL_FRAMEWORK = "import mistralai.workflows as workflows\nfrom mistralai.client.models import OCRResponse\n"
AXIOS_CLIENT = 'import { z } from "zod";\nimport axios from "axios";\n'
SCRIPT_TYPES_ONLY = 'import type { Stripe } from "stripe";\nimport { type ChatCompletion } from "openai";\n'
SCRIPT_ERRORS_ONLY = 'import { AxiosError } from "axios";\n'
OWN_BACKEND_FETCH = 'export const orders = () => fetch("/api/orders");\n'
REQUIRED_DRIVER = 'const { Pool } = require("pg");\n'
STDLIB_HTTP = "import json\nfrom urllib.request import urlopen\n"
STDLIB_FREE_PORT = (
    "import socket\nfrom urllib.request import getproxies\n\nwith socket.socket() as probe:\n    probe.bind(('', 0))\n"
)
GO_MESSAGES_ONLY = 'package parse\n\nimport "cloud.google.com/go/aiplatform/apiv1beta1/aiplatformpb"\n'
GO_CLIENT = 'package store\n\nimport (\n\t"context"\n\ts3 "github.com/aws/aws-sdk-go-v2/service/s3"\n)\n'


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        ("orders/sync.py", HTTPX_CLIENT, [(2, "warning")]),
        ("orders/services/sync.py", HTTPX_CLIENT, []),
        ("tests/sync.py", HTTPX_CLIENT, []),
        ("orders/test_sync.py", HTTPX_CLIENT, []),
        ("orders/main.py", HTTPX_CLIENT, []),
        ("orders/retry.py", HTTPX_ERRORS_ONLY, []),
        ("orders/fetch.py", STDLIB_HTTP, [(2, "warning")]),
        ("orders/port.py", STDLIB_FREE_PORT, []),
        ("tests/fetch.py", STDLIB_HTTP, []),
        ("orders/store.py", TYPE_CHECKING_IMPORT, []),
        ("orders/llm.py", MISTRAL_CLIENT, [(2, "warning")]),
        ("orders/workflow.py", MISTRAL_FRAMEWORK, []),
        ("orders/gemini.py", "import cohere\nimport google.generativeai as genai\n", [(1, "warning")]),
        ("web/api.ts", AXIOS_CLIENT, [(2, "warning")]),
        ("web/api.test.ts", AXIOS_CLIENT, []),
        ("web/billing.ts", SCRIPT_TYPES_ONLY, []),
        ("web/errors.ts", SCRIPT_ERRORS_ONLY, []),
        ("web/orders.tsx", OWN_BACKEND_FETCH, []),
        ("web/db.js", REQUIRED_DRIVER, [(1, "warning")]),
        ("store/s3.go", GO_CLIENT, [(5, "warning")]),
        ("parse/vertex.go", GO_MESSAGES_ONLY, []),
        ("cmd/store/main.go", GO_CLIENT, []),
    ],
)
def test_client_imports_outside_services(
    run_pristine: RunPristine, path: str, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, "CR-8") == expected


def test_one_finding_lists_every_client_library(run_pristine: RunPristine) -> None:
    source = "import redis\nimport boto3\nimport redis.asyncio\n"
    _, report = run_pristine({"orders/cache.py": source})
    messages = [finding["message"] for finding in report["findings"] if finding["rule_id"] == "CR-8"]
    assert len(messages) == 1
    assert "redis, boto3 outside" in messages[0]
