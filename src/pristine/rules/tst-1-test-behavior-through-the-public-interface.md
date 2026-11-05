# TST-1 Test Behavior Through the Public Interface

A test reaches the code only through its public interface: it feeds inputs and observes outcomes visible from outside. Outcomes include return values, persisted state, emitted events, and required calls to external systems. Reading a private attribute, counting the members of a module, or asserting that a constant equals what the source assigns it restates the source and tests nothing. A fake that replaces an external system keeps its contract: the same errors, constraints, and limits.

This rule owns what a test observes. [TST-7](tst-7-expected-results-come-from-an-independent-oracle.md) owns how the test determines the correct outcome.

The suite is correct on two sides: a change in behavior breaks a test, and a refactor that changes no behavior breaks nothing. A regression that slips through is a hole in the suite. A refactor that turns a test red reveals a brittle test. Both are defects.

A test's name states the behavior it pins: `test_charge_stops_after_max_retries`, never `test_case_3`.

Never retest what you do not own. The standard library, the framework, and the ORM are contracts of their maintainers. Your configuration, mappings, adapters, and assumptions at those boundaries are your contract, and you test them through the behavior they produce.

Prefer fakes at the edge of the system. The clock, SMTP, and a payment gateway are replaced with fakes. A stable owned boundary may use a test double when the interaction itself is part of the contract. Mocking an internal unit only to mirror the wiring of the moment tests an implementation detail.

A fake earns trust only while it behaves like the system it replaces. A fake gateway that accepts a negative amount the real gateway rejects lets a broken caller pass. When important tests rely on a fake, a contract test runs the same assertions against the real adapter in `make check-all` (see [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md)), so the fake cannot drift. A language model is the exception: tests never call it, and evals measure it (see [TST-8](tst-8-model-quality-is-measured-by-evals-code-by-deterministic-tests.md)).

Injected collaborators make fakes possible (see [CO-4](co-4-clear-interfaces.md)), and focused units make behavior observable at all (see [CO-2](co-2-small-focused-units.md)).

## Bad

```python
def test_charge_stops_after_max_retries():
    gateway = AlwaysFailingPaymentGateway()
    result = retry_charge(gateway, amount_in_cents=4200)
    assert result._attempt_count == 5
```

The assertion reaches into private retry state. Renaming or removing the counter breaks the test even when charging still stops after five attempts.

## Good

```python
def test_charge_stops_after_max_retries():
    gateway = AlwaysFailingPaymentGateway()
    result = retry_charge(gateway, amount_in_cents=4200)
    assert result.status == "failed"
    assert gateway.charge_attempts == 5
```

Break the stopping condition and it fails. Restructure the retry loop completely and it passes. It pins the contract: charging stops after the configured number of attempts.
