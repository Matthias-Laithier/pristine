import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CO-13"
PYTHON_MODULE = """import logging
import os
import re
import threading

logger = logging.getLogger(__name__)
SLUG = re.compile(r"[a-z]+")
API_KEY = os.environ["PAYMENTS_API_KEY"]
TEMPLATE = open("invoice.txt").read()
print("loading payments")
threading.Thread(target=logger.info).start()


@app.get("/invoices")
def list_invoices():
    return os.getenv("REGION")


class Settings:
    region = os.environ.get("REGION")


if __name__ == "__main__":
    print(API_KEY)
"""
SCRIPT_MODULE = """import "dotenv/config";
import { PrismaClient } from "@prisma/client";

export const apiUrl = process.env.API_URL;
export const publicUrl = process.env.NEXT_PUBLIC_URL;
const prisma = new PrismaClient();
console.log("loaded");
export const readKey = () => process.env.API_KEY;
export const readInvoice = Effect.fn("readInvoice")(function* () { yield* fs.readFile("invoice.txt"); });
"""
ENVIRONMENT_READ = "API_KEY = os.environ['PAYMENTS_API_KEY']\n"
SCRIPT_ENVIRONMENT_READ = "export const apiUrl = process.env.API_URL;\n"


def test_python_module_level_work(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"payments.py": PYTHON_MODULE})
    assert rule_findings(report, RULE_ID) == [(8, "error"), (9, "error"), (10, "warning"), (11, "error")]


def test_script_module_level_work(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"payments.ts": SCRIPT_MODULE})
    assert rule_findings(report, RULE_ID) == [(1, "error"), (4, "error"), (6, "error"), (7, "warning")]


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("__main__.py", ENVIRONMENT_READ),
        ("conftest.py", ENVIRONMENT_READ),
        ("migrations/env.py", ENVIRONMENT_READ),
        ("tests/test_payments.py", ENVIRONMENT_READ),
        ("client-e2e/scenarios/startup.py", ENVIRONMENT_READ),
        ("seed_invoices.py", f"#!/usr/bin/env python3\n{ENVIRONMENT_READ}"),
        ("vite.config.ts", SCRIPT_ENVIRONMENT_READ),
        ("payments.test.ts", SCRIPT_ENVIRONMENT_READ),
    ],
)
def test_entrypoints_and_tests_are_exempt(run_pristine: RunPristine, path: str, source: str) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []
