import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "DEP-5"
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
    assert rule_findings(report, CHECK_ID) == [
        (8, "error"),
        (9, "error"),
        (10, "warning"),
        (11, "error"),
        (20, "error"),
    ]


def test_script_module_level_work(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"payments.ts": SCRIPT_MODULE})
    assert rule_findings(report, CHECK_ID) == [(1, "error"), (4, "error"), (6, "error"), (7, "warning")]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            (
                "@configure(os.getenv('DECORATOR'))\n"
                "class Settings(base(open('base.txt')), metaclass=configure(os.getenv('META'))):\n"
                "    class Region:\n"
                "        value = os.getenv('REGION')\n"
                "    @configure(open('method.txt'))\n"
                "    def load(self, region=os.getenv('DEFAULT')):\n"
                "        return open('body.txt')\n"
            ),
            [(1, "error"), (2, "error"), (4, "error"), (5, "error"), (6, "error")],
        ),
        (
            (
                "@configure(open('decorator.txt'))\n"
                "async def load(key: os.getenv('ANNOTATION') = open('default.txt'), /,\n"
                "               *, region=os.getenv('KEYWORD')) -> os.getenv('RETURN'):\n"
                "    @configure(open('nested-decorator.txt'))\n"
                "    def nested(region=os.getenv('NESTED_DEFAULT')):\n"
                "        return open('nested-body.txt')\n"
                "    class RuntimeSettings:\n"
                "        region = os.getenv('NESTED_CLASS')\n"
                "    return open('body.txt')\n"
                "reader = lambda key=open('lambda-default.txt'): os.getenv('LAMBDA_BODY')\n"
            ),
            [(1, "error"), (2, "error"), (3, "error"), (10, "error")],
        ),
        (
            (
                "@app.get('/invoices')\n"
                "class Settings[Region: os.getenv('BOUND')]:\n"
                "    @staticmethod\n"
                "    def load(key: open('annotation.txt'), region: os.getenv('ANNOTATION') = 'local') -> open('return.txt'):\n"
                "        return os.getenv('BODY')\n"
                "if __name__ == '__main__':\n"
                "    @configure(open('main-decorator.txt'))\n"
                "    class RuntimeSettings:\n"
                "        region = os.getenv('MAIN_CLASS')\n"
            ),
            [],
        ),
    ],
)
def test_python_definition_evaluation(run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"payments.py": source})
    assert rule_findings(report, CHECK_ID) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            (
                "class Settings:\n"
                "    region: os.getenv('REGION') = 'local'\n"
                "    region_type: open('annotation.txt')\n"
                "    loaded: str = os.getenv('LOADED')\n"
            ),
            [(4, "error")],
        ),
        (
            (
                "class Settings:\n"
                "    regions = (os.getenv('REGION') for _ in range(3))\n"
                "    filtered = (_ for _ in range(3) if open('filter.txt') for item in open('later.txt'))\n"
                "    loaded = (_ for _ in open('regions.txt'))\n"
                "    eager = [os.getenv('REGION') for _ in range(3)]\n"
            ),
            [(4, "error"), (5, "error")],
        ),
    ],
)
def test_python_deferred_class_expressions(
    run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]
) -> None:
    _, report = run_pristine({"payments.py": source})
    assert rule_findings(report, CHECK_ID) == expected


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
    assert rule_findings(report, CHECK_ID) == []
