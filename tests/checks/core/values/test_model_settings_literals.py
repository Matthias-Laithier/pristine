import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CR-18"
HARDCODED_SETTINGS = """from mistralai import Mistral

SUMMARY_MODEL = "mistral-small-latest"


def summarize_ticket(client, ticket):
    return client.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": ticket.body}],
        temperature=0.2,
        top_p=0.9,
    )


def summarize_invoice(client, invoice):
    return client.chat.complete(model=SUMMARY_MODEL, messages=[{"role": "user", "content": invoice.text}])


def draft_reply(client, ticket):
    return client.responses.create(model="openai/gpt-4o", input=ticket.body)


def reasoning_client():
    return ChatOpenAI(model="o3-mini")
"""
CONFIGURED_SETTINGS = """from django.db import models

TICKET_MODEL = "support.Ticket"


def summarize_ticket(client, settings, ticket):
    return client.chat.complete(
        model=settings.summary_model,
        messages=[{"role": "user", "content": ticket.body}],
        temperature=settings.summary_temperature,
    )


def extract_fields(client, settings, ticket):
    return client.chat.complete(model=settings.extraction_model, messages=ticket.messages, temperature=0, top_p=1)


def create_ticket_link(registry, ticket):
    return registry.create(model=TICKET_MODEL, record=ticket)


def create_order(warehouse, order):
    return warehouse.create(model=order.model, temperature=4)


def summarize_order(client, settings, order):
    return client.chat.complete(model=settings.summary_model, messages=order.messages, temperature=0.3)
"""
SDK_CLIENT_CALLS = """from mistralai import Mistral
from openai import AsyncOpenAI


class TicketSummarizer:
    def __init__(self, api_key):
        self.client = Mistral(api_key=api_key)

    def summarize(self, settings, ticket):
        return self.client.chat.complete(model=settings.summary_model, messages=ticket.messages, temperature=0.3)


def classify_ticket(client: Mistral, ticket):
    return client.classifiers.classify(model="ticket-router-v2", inputs=[ticket.body])


async def draft_reply(api_key, ticket):
    async with AsyncOpenAI(api_key=api_key) as client:
        return await client.responses.create(model="support-replies", input=ticket.body)
"""
LITERAL_MODEL_CALL = """def summarize_ticket(client, ticket):
    return client.chat.complete(model="mistral-large-latest", messages=ticket.messages)
"""


def test_literal_models_and_sampling_settings_are_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"support.py": HARDCODED_SETTINGS})
    expected = [(8, "warning"), (10, "warning"), (11, "warning"), (16, "warning"), (20, "warning"), (24, "warning")]
    assert rule_findings(report, RULE_ID) == expected


def test_configured_neutral_and_unrelated_values_are_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"support.py": CONFIGURED_SETTINGS})
    assert rule_findings(report, RULE_ID) == []


def test_any_literal_on_a_model_sdk_client_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"support.py": SDK_CLIENT_CALLS})
    assert rule_findings(report, RULE_ID) == [(10, "warning"), (14, "warning"), (19, "warning")]


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("tests/test_support.py", LITERAL_MODEL_CALL),
        ("backfill_summaries.py", f"#!/usr/bin/env python3\n{LITERAL_MODEL_CALL}"),
    ],
)
def test_tests_and_shebang_scripts_are_exempt(run_pristine: RunPristine, path: str, source: str) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []


@pytest.mark.parametrize(
    "path", ["support.py", "evals/support_quality.py", "examples/support.py", "scripts/backfill.py"]
)
def test_literal_model_is_reported_whatever_the_folder(run_pristine: RunPristine, path: str) -> None:
    _, report = run_pristine({path: LITERAL_MODEL_CALL})
    assert rule_findings(report, RULE_ID) == [(2, "warning")]
