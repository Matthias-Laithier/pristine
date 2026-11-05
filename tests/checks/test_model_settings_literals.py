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


def demo_label(form):
    return form.render(model="mistral-large-latest")
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


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("tests/test_support.py", LITERAL_MODEL_CALL),
        ("evals/support_quality.py", LITERAL_MODEL_CALL),
        ("examples/support.py", LITERAL_MODEL_CALL),
        ("scripts/backfill_summaries.py", LITERAL_MODEL_CALL),
        ("backfill_summaries.py", f"#!/usr/bin/env python3\n{LITERAL_MODEL_CALL}"),
    ],
)
def test_tests_evals_examples_and_scripts_are_exempt(run_pristine: RunPristine, path: str, source: str) -> None:
    _, report = run_pristine({path: source})
    assert rule_findings(report, RULE_ID) == []


def test_literal_model_in_an_application_module_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"support.py": LITERAL_MODEL_CALL})
    assert rule_findings(report, RULE_ID) == [(2, "warning")]
