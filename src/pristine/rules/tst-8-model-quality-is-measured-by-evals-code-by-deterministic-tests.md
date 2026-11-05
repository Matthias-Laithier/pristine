# TST-8 Model Quality Is Measured by Evals, Code by Deterministic Tests

Code that calls a language model has two separate verdicts. Deterministic tests replace the model with a fake that returns scripted outputs, including malformed, truncated, refused, and tool-calling outputs, and pin how the code handles each. Evals call the real model on a versioned dataset, score every case, and compare the aggregate with a threshold and the previous baseline. Tests never call a real model. Evals never judge a single output.

A test against a live model is slow, costly, and changes verdict with every model update (see [TST-6](tst-6-tests-are-deterministic.md)). A green suite with a fake model proves parsing and control flow, and says nothing about the quality of the prompt. Only an eval shows whether a change to a prompt, a model, or a tool definition improved the answers or degraded them.

Run evals through `make eval` on every change to a prompt, a model setting, or a tool definition, and report the score against the baseline. Evals stay outside `make check` and `make check-all` (see [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md)). A scorer follows [TST-7](tst-7-expected-results-come-from-an-independent-oracle.md): a hand-labeled expectation, a deterministic check, or a judge model distinct from the model under test.

## Bad

```python
from openai import OpenAI


def test_summary_mentions_the_overdue_amount():
    summary = summarize_account(OpenAI(), account_with_overdue_invoice())
    assert "120.00 EUR" in summary
```

The verdict changes with sampling and model updates, the run costs money, and one passing answer says nothing about the other answers.

## Good

```python
import pytest


def test_summary_rejects_output_without_the_required_fields():
    model = ScriptedModel(outputs=['{"headline": "Account overdue"}'])
    with pytest.raises(InvalidModelOutput):
        summarize_account(model, account_with_overdue_invoice())
```

The test pins how the code handles a malformed answer, the same way on every run. The quality of real answers is measured by the eval over the labeled dataset.
