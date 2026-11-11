import pytest

from tests.conftest import RunPristine, rule_findings

HTTPX_CLIENT = "import os\nimport httpx\n\nCLIENT = httpx.AsyncClient()\n"
HTTPX_ERRORS_ONLY = "import httpx\n\nRETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)\n"
TYPE_CHECKING_IMPORT = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import boto3\n"
MISTRAL_CLIENT = "from mistralai.workflows import workflow\nfrom mistralai.client import Mistral\n\nMistral()\n"
MISTRAL_FRAMEWORK = (
    "import mistralai.workflows as workflows\nfrom mistralai.client.models import OCRResponse\n\n"
    "workflows.workflow.define()\nOCRResponse.model_validate(payload)\n"
)
AXIOS_CLIENT = 'import { z } from "zod";\nimport axios from "axios";\naxios.get("/orders");\n'
SCRIPT_TYPES_ONLY = 'import type { Stripe } from "stripe";\nimport { type ChatCompletion } from "openai";\n'
SDK_SCHEMA_ONLY = (
    'import { CardSchema } from "@mistralai/mistralai/models/components";\nconst card = CardSchema.safeParse(value);\n'
)
NAMED_CLIENT = 'import { S3Client } from "@aws-sdk/client-s3";\nconst storage = new S3Client({});\n'
SCRIPT_ERRORS_ONLY = (
    'import axios, { AxiosError } from "axios";\nif (error instanceof AxiosError) throw new AxiosError("failed");\n'
)
OWN_BACKEND_FETCH = 'export const orders = () => fetch("/api/orders");\n'
REQUIRED_DRIVER = 'const { Pool } = require("pg");\nconst pool = new Pool();\n'
STDLIB_HTTP = "import json\nfrom urllib.request import urlopen\n\nurlopen(url)\n"
STDLIB_FREE_PORT = (
    "import socket\nfrom urllib.request import getproxies\n\nwith socket.socket() as probe:\n    probe.bind(('', 0))\n"
)
REDIS_ERRORS_ONLY = (
    "import redis\nfrom redis.exceptions import ConnectionError\n\n"
    "try:\n    store()\nexcept (ConnectionError, redis.RedisError):\n    raise redis.RedisError('down')\n"
)
ANNOTATION_ONLY = (
    "from openai import OpenAI\n\n\ndef summarize(client: OpenAI):\n    return client.chat.completions.create()\n"
)
PASSED_THROUGH = "from openai import OpenAI\n\n\ndef register(client: OpenAI):\n    return {'model': client}\n"
INJECTED_ATTRIBUTE = (
    "import httpx\n\n\nclass OrderFeed:\n    def __init__(self, http: httpx.AsyncClient | None):\n"
    "        self.http = http\n\n    async def load(self):\n        return await self.http.get('/orders')\n"
)
ANNOTATED_FIELD = (
    "from mistralai import Mistral\n\n\nclass Summarizer:\n    model: Mistral\n\n"
    "    def run(self):\n        return self.model.chat.complete(model='small')\n"
)
SCRIPT_INJECTED = (
    'import type OpenAI from "openai";\nimport * as pg from "pg";\n\nexport class OrderStore {\n'
    '  constructor(private readonly pool: pg.Pool) {}\n  load() { return this.pool.query("select 1"); }\n}\n'
    "export const ask = (client: OpenAI) => client.chat.completions.create({});\n"
)
SCRIPT_PASSED_THROUGH = (
    'import type { AxiosInstance } from "axios";\nexport const keep = (http: AxiosInstance) => [http];\n'
)


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
        (
            "orders/gemini.py",
            "import cohere\nimport google.generativeai as genai\n\ncohere.Client()\n",
            [(1, "warning")],
        ),
        ("orders/cache.py", REDIS_ERRORS_ONLY, []),
        ("orders/summary.py", ANNOTATION_ONLY, [(4, "warning")]),
        ("orders/registry.py", PASSED_THROUGH, []),
        ("orders/feed.py", INJECTED_ATTRIBUTE, [(5, "warning")]),
        ("orders/summarizer.py", ANNOTATED_FIELD, [(5, "warning")]),
        ("web/store.ts", SCRIPT_INJECTED, [(5, "warning")]),
        ("web/keep.ts", SCRIPT_PASSED_THROUGH, []),
        ("web/api.ts", AXIOS_CLIENT, [(2, "warning")]),
        ("web/api.test.ts", AXIOS_CLIENT, []),
        ("web/billing.ts", SCRIPT_TYPES_ONLY, []),
        ("web/errors.ts", SCRIPT_ERRORS_ONLY, []),
        ("web/cards.ts", SDK_SCHEMA_ONLY, []),
        ("web/storage.ts", NAMED_CLIENT, [(1, "warning")]),
        ("web/orders.tsx", OWN_BACKEND_FETCH, []),
        ("web/db.js", REQUIRED_DRIVER, [(1, "warning")]),
    ],
)
def test_client_imports_outside_services(
    run_pristine: RunPristine, path: str, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, "CR-8") == expected


def test_one_finding_lists_every_client_library(run_pristine: RunPristine) -> None:
    source = "import redis\nimport boto3\nimport redis.asyncio\n\nredis.asyncio.Redis()\nboto3.client('s3')\n"
    _, report = run_pristine({"orders/cache.py": source})
    messages = [finding["message"] for finding in report["findings"] if finding["rule_id"] == "CR-8"]
    assert len(messages) == 1
    assert "boto3, redis outside" in messages[0]
